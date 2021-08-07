import re
from dateparser import parse
from datetime import datetime

from suzieq.poller.services.service import Service
from suzieq.utils import (expand_nxos_ifname, get_timestamp_from_cisco_time,
                          get_timestamp_from_junos_time)


import numpy as np


class RoutesService(Service):
    """routes service. Different class because vrf default needs to be added"""

    def _fix_ipvers(self, entry):
        if ':' in entry['prefix']:
            entry['ipvers'] = 6
        else:
            entry['ipvers'] = 4

    def _common_data_cleaner(self, processed_data, raw_data):
        for entry in processed_data:
            self._fix_ipvers(entry)

        return processed_data

    def _clean_eos_data(self, processed_data, raw_data):
        '''Massage EVPN routes'''
        for entry in processed_data:
            if entry['nexthopIps']:
                nexthop = entry['nexthopIps'][0]
                if 'vtepAddr' in nexthop:
                    nexthop = entry['nexthopIps'][0]
                    entry['nexthopIps'] = [nexthop['vtepAddr']]
                    entry['oifs'] = ['_nexthopVrf:default']
            elif entry.get('_vtepAddr', []):
                entry['nexthopIps'] = entry['_vtepAddr']
                entry['oifs'] = len(entry['nexthopIps']) * \
                    ['_nexthopVrf:default']
            entry['protocol'] = entry['protocol'].lower()
            entry['preference'] = int(entry.get('preference', 0))
            entry['metric'] = int(entry.get('metric', 0))
            self._fix_ipvers(entry)

        return processed_data

    def _clean_linux_data(self, processed_data, raw_data):
        """Clean Linux ip route data"""

        for entry in processed_data:
            entry["vrf"] = entry["vrf"] or "default"
            entry["metric"] = entry["metric"] or 20
            entry['preference'] = entry['metric']
            for ele in ["nexthopIps", "oifs"]:
                entry[ele] = entry[ele] or [""]
            entry['hardwareProgrammed'] = 'unknown'
            entry["weights"] = entry["weights"] or [1]
            if entry['prefix'] == 'default':
                if any(':' in x for x in entry['nexthopIps']):
                    entry['prefix'] = '::0/0'
                else:
                    entry['prefix'] = '0.0.0.0/0'

            self._fix_ipvers(entry)

            if '/' not in entry['prefix']:
                if entry['ipvers'] == 6:
                    entry['prefix'] += '/128'
                else:
                    entry['prefix'] += '/32'
            if not entry["action"]:
                entry["action"] = "forward"
            elif entry["action"] == "blackhole":
                entry["oifs"] = ["blackhole"]

            entry['inHardware'] = True  # Till the offload flag is here

        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_junos_data(self, processed_data, raw_data):
        """Clean VRF name in JUNOS data"""

        drop_entries_idx = []
        prefix_entries = {}

        for i, entry in enumerate(processed_data):

            if '_vtepAddr' in entry:
                # Get the entry from the prefix DB. We have the correct NH
                pentry = prefix_entries.get(entry['prefix'], None)
                if not pentry:
                    drop_entries_idx.append(i)
                    continue
                pentry['nexthopIps'] = [entry['_vtepAddr']]
                pentry['oifs'] = ['_nexthopVrf:default']
                drop_entries_idx.append(i)
                continue

            vrf = entry.pop("vrf")[0]['data']
            if vrf == "inet.0":
                vrf = "default"
                vers = 4
            elif vrf == "inet6.0":
                vrf = "default"
                vers = 6
            else:
                words = vrf.split('.')
                vrf = words[0]
                family = words[1]
                if family == "inet":
                    vers = 4
                elif family == "inet6":
                    vers = 6
            entry['vrf'] = vrf
            entry['ipvers'] = vers

            if entry['_localif']:
                entry['oifs'] = [entry['_localif']]

            entry['protocol'] = entry['protocol'].lower()
            if entry['_rtlen'] != 0:
                drop_entries_idx.append(i)

            if entry.get('asPathList', []):
                entry['asPathList'] = entry['asPathList'].split()

            prefix_entries[entry['prefix']] = entry

            lastChange = entry.get('statusChangeTimestamp', [''])
            if lastChange:
                entry['statusChangeTimestamp'] = get_timestamp_from_junos_time(
                    lastChange, raw_data[0]['timestamp']/1000)
            else:
                entry['statusChangeTimestamp'] = 0

            entry['active'] = entry['_activeTag'] in ['*', '@', '#']

            entry['preference'] = int(entry.get('preference', 0))
            entry['metric'] = int(entry.get('metric', 0))
            if entry.get('nexthopIps', '') == [None]:
                entry['nexthopIps'] = ['']

            entry['action'] = entry.get('action', '').lower()
            if entry['action'] == "discard":
                entry['action'] = 'drop'
            entry.pop('_localif')
            entry.pop('_activeTag')

        processed_data = np.delete(processed_data,
                                   drop_entries_idx).tolist()

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):

        drop_indices = []

        for i, entry in enumerate(processed_data):
            if 'prefix' not in entry or not entry['prefix']:
                drop_indices.append(i)
                continue

            entry['protocol'] = entry.get('protocol', '').split('-')[0]

            entry['metric'] = [int(x) if x is not None else 0
                               for x in entry.get('metric', [])]
            entry['metric'] = entry['metric'][0]
            try:
                entry['preference'] = int(entry.get('preference', [0])[0])
            except ValueError:
                entry['preference'] = 0

            oiflist = []
            for oif in entry['oifs']:
                if oif:
                    oif = expand_nxos_ifname(oif)
                    oiflist.append(oif)
            entry['oifs'] = oiflist

            if not entry['oifs']:
                oiflist = []
                for nhv in entry.get('_nexthopVrf', []):
                    if nhv:
                        oiflist.append(f'_nexthopVrf:{nhv}')
                entry['oifs'] = oiflist

            if 'discard' in entry.get('_routeAction', []):
                entry['action'] = 'drop'
            else:
                entry['action'] = 'forward'

            # Right now we only store the timestamp of the first NH change
            # The correct thing to do is to take all NH timestamps, and take
            # the latest one: TODO
            lastChange = entry.get('statusChangeTimestamp', [''])[0]
            if lastChange:
                entry['statusChangeTimestamp'] = get_timestamp_from_cisco_time(
                    lastChange, raw_data[0]['timestamp']/1000)
            else:
                entry['statusChangeTimestamp'] = 0

            self._fix_ipvers(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_iosxr_data(self, processed_data, raw_data):

        proto_map = {'C': ['connected', ''], 'S': ['static', ''],
                     'R': ['rip', ''], 'B': ['bgp', ''],
                     'D': ['eigrp', ''], 'EX': ['eigrp', 'external'],
                     'O': ['ospf' ''], 'O IA': ['ospf', 'interarea'],
                     'O N1': ['ospf', 'nssa-ext1'],
                     'O N2': ['ospf', 'nssa-ext2'],
                     'O E1': ['ospf', 'external-1'],
                     'O E2': ['ospf', 'external-2'], 'E': ['igp', ''],
                     'i': ['isis', ''], 'i L1': ['isis', 'level-1'],
                     'i L2': ['isis', 'level-2'],
                     'i ia': ['isis', 'interarea'],
                     'i su': ['isis', 'summary-null'], 'U': ['static', 'user'],
                     'o': ['odr', ''], 'L': ['local', ''], 'G': ['dagr', ''],
                     'l': ['lisp', ''], 'M': ['mobile', ''],
                     'a': ['application', ''], 'r': ['rpl', ''],
                     't': ['te', ''],
                     'A': ['access', ''], '!': ['backup', '']}

        for entry in processed_data:
            entry['protocol'] = proto_map.get(entry.get('protocol', '')[0],
                                              entry.get('protocol', ''))[0]
            if not entry['vrf']:
                entry['vrf'] = 'default'
            if entry.get('nexthopvrf', ''):
                entry['oifs'] = [f'_nexthopVrf:{entry["nexthopvrf"]}']
            if entry.get('metric', '') == '':
                entry['metric'] = 0
            if entry.get('preference', '') == '':
                entry['preference'] = 0
            self._fix_ipvers(entry)
            entry['hardwareProgrammed'] = 'unknown'
            if not entry.get('action', ''):
                entry['action'] = 'forward'
            else:
                entry['action'] = entry.get('action', '').lower()

            lastchange = entry.get('statusChangeTimestamp', '')
            if lastchange:
                if re.match(r'^\d{2}:\d{2}:\d{2}$', lastchange):
                    lastchange = lastchange.split(':')
                    lastchange = (f'{lastchange[0]} hour '
                                  f'{lastchange[1]}:{lastchange[2]} mins ago')
                lastchange = parse(
                    lastchange,
                    settings={'RELATIVE_BASE':
                              datetime.fromtimestamp(
                                  (raw_data[0]['timestamp'])/1000), })
            if lastchange:
                entry['statusChangeTimestamp'] = lastchange.timestamp()*1000
            else:
                entry['statusChangeTimestamp'] = 0

        return processed_data

    def _clean_iosxe_data(self, processed_data, raw_data):
        processed_data = self._clean_iosxr_data(processed_data, raw_data)

        # Some more IOSXE fixes including:
        #  * lowercasing IPv6 addresses
        #  * adding / to host prefixes
        for entry in processed_data:
            if ':' in entry['prefix']:
                entry['prefix'] = entry['prefix'].lower()
                if '/' not in entry['prefix']:
                    entry['prefix'] += '/128'
            elif '/' not in entry['prefix']:
                entry['prefix'] += '/32'
            newnexthops = []
            for ele in entry['nexthopIps']:
                if ':' in ele:
                    newnexthops.append(ele.lower())
                else:
                    newnexthops.append(ele)
            entry['nexthopIps'] = newnexthops

        return processed_data

    def _clean_ios_data(self, processed_data, raw_data):
        return self._clean_iosxe_data(processed_data, raw_data)
