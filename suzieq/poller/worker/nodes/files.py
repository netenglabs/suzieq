#!/usr/bin/env python3

import asyncio
import re
import json
import logging
from pathlib import Path
from http import HTTPStatus
from datetime import datetime, timezone
import aiofiles

from suzieq.poller.worker.services.service import RsltToken


class FileNode:
    '''Class using run-once=gather snapshot output as mock device input'''

    # pylint: disable=attribute-defined-outside-init
    async def initialize(self, datadir: str):
        '''Load the data to be read from files'''
        self.logger = logging.getLogger(__name__)
        self.data = {}          # The dict of command to output entries
        self.hostname = '_filedata'  # Need this for the services

        self._service_queue = asyncio.Queue()

        await self._load_data(datadir)

    async def _load_data(self, datadir: str):
        """This routine walks the dir loading the data from the files there"""
        p = Path(datadir)
        tasks = []
        for file in p.glob('*.output'):
            tasks.append(self._load_single_file_data(file))

        if not tasks:
            self.logger.error(f'No files to load found in {datadir}')
            return []

        await asyncio.gather(*tasks)

    async def _load_single_file_data(self, file: str):
        """Load gathered data from specified file
        Each entry loaded from the file is a list entry with the format:
        [{'status':...
         'timestamp': ...
         'cmd': ....
         'devtype': ...
         'namespace': ...
         'hostname': ...
         'address': ...
         'version': ...
         'data': ...}]

        If the service consisted of multiple commands, then the format is a
        list, where each entry in the list is of the above format.

        We return a dictionary keyed on the command of the format:
        {cmd1: {curpos: 0, 'entry': <list of entries>},
         cmd2: {curpos: 0, 'entry': <list of entries>,
         ...
        } where each entry in the list is of the individual entry of the input
        format. The basic idea is that when input is requested for a given cmd,
        we return the entry at curpos and increment curpos. When curpos
        exceeds the length of the entries, we reset it back to 0.
        """
        async with aiofiles.open(file, 'r') as f:
            data = await f.read()

        required_keys = ['status', 'timestamp', 'cmd', 'devtype', 'namespace',
                         'hostname', 'address', 'version', 'data',
                         'cmd_timestamp']
        entries = re.split(r'\]\n*\[\n', data)
        entlen = len(entries)

        for i, elem in enumerate(entries):
            newelem = elem.replace('\n', '').strip()
            if entlen > 1:
                if i == 0:
                    newelem = newelem + ']'
                elif i == entlen-1:
                    newelem = '[' + newelem
                else:
                    newelem = '[' + newelem + ']'

            jelem = None
            try:
                jelem = json.loads(newelem)
            except json.decoder.JSONDecodeError:
                # This is a bug in the output of FRR's show evpn vni when
                # there's no EVPN
                if 'show evpn vni detail json' in newelem:
                    newelem = newelem[:-1]
                    jelem = json.loads(newelem)

            if jelem is None:
                self.logger.error(f"Unable to decode JSON in file {file}")
                continue

            # Add backward compatibility for the files not having the
            # cmd_timestamp field
            data_keys = jelem[0].keys()
            if 'cmd_timestamp' not in data_keys:
                for record in jelem:
                    record['cmd_timestamp'] = record['timestamp']

            if not all(key in required_keys for key in data_keys):
                self.logger.error(
                    f'Ignoring entry with missing required key fields {jelem}')
                continue

            key = jelem[0]['cmd'].split('|')[0].strip()

            if key not in self.data:
                self.data[key] = {'curpos': 0, 'entry': []}

            self.data[key]['entry'].append(jelem)

    def post_commands(self, service_callback, svc_defn: dict,
                      cb_token: RsltToken):
        '''Post command outputs back to service that requested them'''

        if cb_token:
            cb_token.nodeQsize = self._service_queue.qsize()
        self._service_queue.put_nowait([service_callback, svc_defn, cb_token])

    async def run(self):
        '''Main workhorse routine, serving data from files based on command'''

        while True:
            request = await self._service_queue.get()
            # request consists of callback fn, service_defn string, cb_token
            if request:
                if not await self.exec_service(request[0], request[1],
                                               request[2]):
                    return

    def _create_result(self, cmd, status, data) -> dict:
        '''Create result object to be posted back to service object'''

        result = {
            "status": status,
            "timestamp": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
            "cmd": cmd,
            "devtype": 'Unknown',
            "namespace": 'Unknown',
            "hostname": self.hostname,
            "address": '0.0.0.0',
            "version": 0,
            "data": data,
        }
        return result

    async def exec_service(self, service_callback, svc_defn: dict,
                           cb_token: RsltToken) -> bool:
        '''This looks up the command, returns the output if available'''

        def _add_cmd_to_cmdset(cmd: str, cmdset: set) -> None:
            """Add a command to the set of commands to be executed"""
            if isinstance(cmd, list):
                # the first command is what we need
                subcmd = cmd[0]['command'].split('|')[0].strip()
                cmdset.add(subcmd)
            else:
                cmdset.add(cmd.split('|')[0].strip())

        cmdset = set()
        for device in svc_defn.keys():
            defn = svc_defn[device]
            if isinstance(defn, list):
                for elem in defn:
                    cmd = elem.get('command', None)
                    if not cmd:
                        continue
                    _add_cmd_to_cmdset(cmd, cmdset)
            else:
                cmd = defn.get('command', None)
                if not cmd:
                    continue

                _add_cmd_to_cmdset(cmd, cmdset)

        nodata = True
        for cmd in cmdset:
            data_entry = self.data.get(cmd, {'entry': []})
            for _ in range(len(data_entry['entry'])):
                retdata = data_entry['entry'].pop()
                await service_callback(retdata, cb_token)
                nodata = False
        if nodata:
            await service_callback([self._create_result(
                cmd, HTTPStatus.NO_CONTENT, [])], cb_token)

        return True
