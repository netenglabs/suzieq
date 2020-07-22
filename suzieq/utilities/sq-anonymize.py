#!/usr/bin/env python

import os
try:
    import simplejson as json
except ModuleNotFoundError:
    import json
import re
import time
import argparse
from pathlib import Path
from netconan.ip_anonymization import IpAnonymizer, IpV6Anonymizer
from netconan.ip_anonymization import anonymize_ip_addr
from collections import defaultdict
from faker import Factory
from jsonpath_ng import parse


class SqAnonymizer(object):
    """Suzieq Gather-Once output Anonymizer Class

    This class implements the anonymizer for the Suzieq run-once=gather output
    format. This anonymizes:
    - IP adddresses (v4 and v6)
    - MAC addresses (in NXOS/EOS or standard format)
    - Hostnames (FQDN or otherwise)

    The workflow is to point either a single file to anonymize or a directory
    of files to anonymize. If its a directory, it only attempts to anonymize
    the files with .output filename and excludes those ending with _anon,output
    For every file in the directory, it produces the equivalent _anon.output
    file that contains the anonymized data. For example, lldp.output is turned
    into lldp_anon.output, device.output is turned into device_anon.output and
    so on. The _anon.output file is in the run-once=gather format.

    Since hostnames can appear anywhere, and do not have a unique format, we
    require users to provide additional information. This information consists
    of a JSONpath expression to the key that holds hostname or a prefix string
    that comes before every hostname. The former is required for JSON outputs &
    the latter for non-JSON output. This model is followed for all data that
    has a non-unique format such as ASNs, VRF names and so on. This is also
    true of MAC addresses in the EOS/NXOS format.

    To ensure the same output when run at different times, the user must
    provide a seed that remains the same across different runs. Otherwise, we
    pick the time of day as the seed which produces different outputs when run
    at diff times.
    """

    def __init__(self, seed: int = 0, preserve_v4_prefix: list = []):
        """Initiaize the anonymizer with a seed"""

        if not seed:
            seed = int(time.time())

        preserve_v4_prefix.append('0.0.0.0/0')
        self.fakeit = Factory.create()
        self.fakeit.seed(seed)
        salt = self.fakeit.password(length=16)
        self.anonv4 = IpAnonymizer(salt, preserve_prefixes=preserve_v4_prefix)
        self.anonv6 = IpV6Anonymizer(salt)
        self.hostmap = {}
        self.macmap = defaultdict(self.fakeit.mac_address)

        # Courtesy of Stackoverflow
        # (https://stackoverflow.com/questions/1418423/the-hostname-regex)
        self.hname_re = r'([a-zA-Z0-9](?:(?:[_a-zA-Z0-9-]*|(?<!-)\.(?![-.]))*[_a-zA-Z0-9]+)?)'

        # This regex will not catch the macaddr in this format:
        # "This is a macaddr:00:01:02:FF:cf:9b"
        # because the macaddr is preceded by :. It will also not match:
        # "00:01:29:AB:cf:47:01" because there's one more group (:01) after
        # the mac address
        self.macaddr_re = r'(?<!:)([0-9a-f]{2}(?::[0-9a-f]{2}){5})(?!:)'

        # NXOS and EOS use this format
        self.nxos_macaddr_re = r'([0-9A-F]{4}\.[0-9A-F]{4}\.[0-9A-F]{4})'

        self.preset_hostname_jpaths = [
            ['TABLE_nbor.ROW_nbor[*].chassis_id'],  # NXOS LLDP
            # NXOS CDP
            ['TABLE_cdp_neighbor_brief_info.ROW_cdp_neighbor_brief_info[*].device_id'],
            ['lldpNeighbors.*.lldpNeighborInfo[*].systemName'],  # EOS
            ['lldp[*].interface[*].chassis[*].name[*].value'],  # lldpd
            ['lldp-neighbors-information.[0].lldp-neighbor-information[*].lldp-remote-system-name.[0].data'],  # JunOS
            ['*.*.neighborCapabilities[*].hostName.advHostName'],  # FRR BGP
            ['*.*.neighborCapabilities[*].hostName.rcvHostName'],  # FRR BGP
            ['*.*.neighborCapabilities[*].hostName.advDomainName'],  # FRR BGP
            ['*.*.neighborCapabilities[*].hostName.rcvDomainName'],  # FRR BGP
            ['host_name']          # NXOS show version output
        ]

        self.preset_hostname_pfxlst = [
            ['SysName:'],
            ['Static hostname:'],
        ]

        # Needed for NXOS and EOS which use the non-standard MACADDR format
        self.preset_macaddr_jpaths = [
            ['configMacAddress'],  # EOS show version output
            ['systemMacAddress'],  # EOS show version output
            ['hwMacAddress'],      # EOS show version output
        ]

    def anonymize(self, file_or_dir: str, anonymize_ip=True,
                  anonymize_mac=True, anonymize_hostname=True,
                  host_prefixes: list = [], host_jpath: list = [],
                  mac_jpath: list = []):
        """Anonymizes the parameters desired in the given input file/dir """

        self.host_jpath = (host_jpath or []) + self.preset_hostname_jpaths
        self.host_pfxlst = (host_prefixes or []) + self.preset_hostname_pfxlst
        self.mac_jpath = (mac_jpath or []) + self.preset_macaddr_jpaths

        if os.path.isfile(file_or_dir):
            self.anonymize_file(file_or_dir, host_prefixes,
                                host_jpath, mac_jpath)
        else:
            # Invoke the command for each file in the directory
            for file in Path(file_or_dir).glob('*.output'):
                if str(file).endswith('_anon.output'):
                    continue
                self.anonymize_file(file, host_prefixes, host_jpath, mac_jpath)

    def anonymize_file(self, file: str, host_pfxlst: list,
                       host_jpath: list, mac_jpath, anonymize_ip=True,
                       anonymize_mac=True, anonymize_hostname=True):
        """Anonymize an individual file"""

        name, suffix = os.path.basename(file).split('.')
        dirname = os.path.dirname(file)
        anon_fname = f'{dirname}/{name}_anon.{suffix}'

        with open(file, 'r') as f:
            data = f.read()

        # Prepare output file by truncating it
        with open(anon_fname, 'w') as f:
            f.write('')

        # The run-once= gather output is not proper JSON. Its
        # written out as a list of entries, but there's no
        # overarching list covering this list. So, we have to
        # handcraft the entries to get them to be readable as
        # JSON. The first entry is missing an ending ']' and the
        # last entry is missing an opening '[' while the intermediate
        # entries are missing both the starting and ending '['.
        entries = re.split(r'\]\n*\[', data)
        entlen = len(entries)
        new_entries = []

        for i, elem in enumerate(entries):
            newelem = elem.replace('\n', '').strip()
            if i == 0:
                newelem = newelem + ']'
            elif i == entlen - 1:
                newelem = '[' + newelem
            else:
                newelem = '[' + newelem + ']'

            try:
                jelem = json.loads(newelem)
                new_entries.append(jelem)
            except Exception as e:
                print(f"JSON load of {i} item failed with error {str(e)}")
                jelem = []

            for item in jelem:
                # Populate the host name anonymizer as much as possible
                item['hostname'] = re.sub(self.hname_re, self.get_anonhost,
                                          item['hostname'])
        for jelem in new_entries:

            for item in jelem:
                if isinstance(item['data'], str):
                    try:
                        jdata = json.loads(item['data'])
                        is_json = True
                    except json.decoder.JSONDecodeError:
                        # non-JSON command output
                        jdata = item['data']
                        is_json = False
                elif isinstance(item['data'], dict):
                    # EOS LLDP output looks like this
                    jdata = item['data']
                    is_json = True

                anondata = ''
                if jdata:
                    if is_json:
                        anondata = json.dumps(jdata)
                    else:
                        anondata = jdata

                if anonymize_mac:
                    anondata = self.anonymize_mac(
                        self.macmap, anondata, is_json)

                if anonymize_ip:
                    anondata = self.anonymize_ip(item, anondata)

                if anonymize_hostname:
                    anondata = self.anonymize_hostname(item, anondata,
                                                       is_json)

                if anondata:
                    item['data'] = anondata

            # Append each entry
            with open(anon_fname, 'a') as f:
                f.write(json.dumps(jelem, indent=4))

    def anonymize_ip(self, item: dict, anondata: str) -> str:
        """Anonymize the IP address in the data and in the item header

        Anonymize the IP addresses, v4 and v6, in the supplied data. Also
        anonymize the IP address in the data header. Both are specific to the
        run-once=gather format of Suzieq
        """
        item['address'] = anonymize_ip_addr(self.anonv4, item['address'])
        item['address'] = anonymize_ip_addr(self.anonv6, item['address'])

        if not anondata:
            return anondata

        anondata = anonymize_ip_addr(self.anonv4, anondata, False)
        anondata = anonymize_ip_addr(self.anonv6, anondata, False)

        return anondata

    def anonymize_mac(self, macmap, anondata: str, is_json: bool) -> str:
        """Anonymize the MAC address in the data and in the item header

        Both are specific to the run-once=gather format of Suzieq
        """
        def nxos_mac_sub(match):
            newmac = macmap[match.group(1)]
            newmac = newmac.split(':')
            newmac = (''.join(newmac[0:2]) + '.' + ''.join(newmac[2:4]) + '.' +
                      ''.join(newmac[4:]))
            return newmac

        def jp_anon_macaddr(orig_v, orig_kv, orig_k):
            """JSONPATH update macaddress in NXOS/EOS format"""
            orig_kv[orig_k] = macmap[orig_v]

        if not anondata:
            return

        anondata = re.sub(self.macaddr_re,
                          lambda x: macmap[x.group(1)],
                          anondata, flags=re.IGNORECASE)

        anondata = re.sub(self.nxos_macaddr_re, nxos_mac_sub, anondata,
                          flags=re.IGNORECASE)

        if is_json:
            janon = json.loads(anondata)
            for path in self.mac_jpath:
                jp = parse(path[0])
                jp.update(janon, jp_anon_macaddr)
            anondata = json.dumps(janon)

        return anondata

    def get_anonhost(self, host: str) -> str:
        """Check various conditions to return the anonymized hostname.

        Sometimes hostnames are present without FQDN and sometimes with.
        We want to map them consistently to the same anonymized hostname.
        We won't know which format we'll encounter first and so we have to
        handle that as well. Hence this routine
        """

        if not host:
            return host

        if isinstance(host, re.Match):
            orighost = host.group(1)
        else:
            orighost = host

        helem = orighost.split('.')
        anonhost = self.hostmap.get(orighost, '')
        if not anonhost and len(helem) > 1:
            anonhost = self.hostmap.get(helem[0], '')

        if not anonhost:
            anonhost = self.fakeit.hostname()
            if len(helem) > 1:
                self.hostmap[orighost] = anonhost
                self.hostmap[helem[0]] = anonhost
            else:
                self.hostmap[orighost] = anonhost

        if len(helem) == 1:
            return anonhost.split('.')[0]
        else:
            return anonhost

    def anonymize_hostname(self, item: dict, anondata: str, is_json: bool) \
            -> str:
        """Anonymize the hostname in the item header and the data

        """

        def anon_hostname(match):
            newhostname = self.get_anonhost(match.group(1))
            if is_json:
                return f'"{kwd[0]}": "{newhostname}"'
            else:
                return f'{kwd[0]} {newhostname}'

        def jp_anon_hostname(orig_v, orig_kv, orig_k):
            """JSONPATH update hostname"""
            if orig_v == 'n/a':  # handle null domainname in FRR BGP
                return
            orig_kv[orig_k] = self.get_anonhost(orig_v)

        if not anondata:
            return anondata

        if is_json:
            janon = json.loads(anondata)
            for path in self.host_jpath:
                jp = parse(path[0])
                jp.update(janon, jp_anon_hostname)
            anondata = json.dumps(janon)
        else:
            for kwd in self.host_pfxlst:
                hpat = r'{}\s+{}'.format(kwd[0], self.hname_re)
                anondata = re.sub(hpat, anon_hostname, anondata)

        # The hostname shows up in strange places and so do one more pass with
        # their hostnames we have to see if we can catch those entries
        for hostname in self.hostmap:
            anondata = anondata.replace(hostname, self.hostmap[hostname])
        return anondata

    def dump_mappings(self, file_or_dir) -> None:
        """Dump the mappings of various fields into a file"""

        if os.path.isdir(file_or_dir):
            dirname = file_or_dir
        else:
            dirname = os.path.dirname(os.path.abspath(file_or_dir))

        with open(f'{dirname}/mapping.txt', 'w') as f:
            for k, v in self.hostmap.items():
                f.write(f'{k}\t{v}\n')
            for k, v in self.macmap.items():
                f.write(f'{k}\t{v}\n')
            self.anonv4.dump_to_file(f)
            self.anonv6.dump_to_file(f)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description="Anonymize suzieq run-once data files")
    parser.add_argument(
        "-i",
        "--input",
        type=str, required=True,
        help="Directory of files or single File to anonymize",
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=str,
        help="Value to seed the randomizer with"
    )
    parser.add_argument(
        "-ph",
        "--host-prefix",
        nargs="+", action='append',
        help="Keywords preceding hostname to anonymize hostname (non-JSON output)",
    )
    parser.add_argument(
        "-PH",
        "--host-jpath",
        nargs="+", action='append',
        help=("JSON path to get to hostname in JSON output (use option "
              "multiple times to provide multiple values)")
    )
    parser.add_argument(
        "-PM",
        "--mac-jpath",
        nargs="+", action='append',
        help=("JSON path to get to NXOS/EOS Macaddr in JSON output"
              "Use option multiple times to provide multiple values")
    )
    parser.add_argument(
        "-ip",
        "--preserve-v4-prefixes",
        nargs="+", action='append',
        help=("IP address prefix to NOT anonymize (default is always incl)"
              "Use option multiple times to provide multiple values")
    )
    userargs = parser.parse_args()

    anonymizer = SqAnonymizer(userargs.seed)
    anonymizer.anonymize(userargs.input, host_prefixes=userargs.host_prefix,
                         host_jpath=userargs.host_jpath,
                         mac_jpath=userargs.mac_jpath)
    anonymizer.dump_mappings(userargs.input)
