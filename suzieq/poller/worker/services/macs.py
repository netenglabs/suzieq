import re

import numpy as np

from suzieq.poller.worker.services.service import Service
from suzieq.shared.utils import convert_macaddr_format_to_colon
from suzieq.shared.utils import (expand_nxos_ifname, expand_eos_ifname,
                                 expand_ios_ifname)


class MacsService(Service):
    """Mac address service. Different class because of macaddr not in key"""

    def get_key_flds(self):
        """The MAC table in Linux can have weird keys"""
        return ['vlan', 'macaddr', 'oif', 'remoteVtepIp', 'bd']

    def _add_mackey_protocol(self, entry):
        """Construct a key field that is unique.

        This is because of the following cases:
        1. Cumulus has all 0 MAC address with different remoteVtepIP, but
           same VLAM, as ingress replication entries.
        2. Cumulus has interface MAC entries with the same MAC and VLAN 0
        3. Juniper's VPLS entries have only BD, no VLAN
        4. The remaining regular entries where VLAN disambiguates a MAC.
        """
        # Make VLAN int first
        vlan = entry.get('vlan', '0')
        if vlan:
            if isinstance(vlan, str):
                if not vlan.isnumeric():
                    vlan = '0'

                entry['vlan'] = int(vlan)
        else:
            vlan = 0
            entry['vlan'] = 0

        if entry.get('bd', ""):
            if not entry.get('vlan', 0):
                entry['mackey'] = entry['bd']
            else:
                entry['mackey'] = f'{entry["bd"]}-{entry["vlan"]}'
        else:
            if entry.get("remoteVtepIp", ''):
                if entry['macaddr'] == '00:00:00:00:00:00':
                    entry['mackey'] = f'{entry["oif"]}-{entry["remoteVtepIp"]}'
                elif entry['vlan']:
                    entry['mackey'] = entry['vlan']
                else:
                    entry['mackey'] = entry['oif']
            else:
                if vlan:
                    if entry['flags'] in ['static', 'permanent', 'router']:
                        entry['mackey'] = f'{vlan}-{entry["oif"]}'
                    else:
                        entry['mackey'] = vlan
                else:
                    if entry['flags'] in ['static', 'permanent', 'router']:
                        entry['mackey'] = f'{entry["oif"]}'
                    else:
                        entry['mackey'] = '0'

    def _clean_linux_data(self, processed_data, _):
        drop_indices = []
        macentries = {}
        for i, entry in enumerate(processed_data):
            macaddr = entry.get('macaddr', None)
            oif = entry.get('oif', '')
            if macaddr and (macaddr != "00:00:00:00:00:00"):
                key = f'{macaddr}-{oif}'

                old_entry = macentries.get(key, None)
                if not old_entry:
                    macentries[key] = entry
                elif not (old_entry['vlan'] and entry['vlan']):
                    # Ensure we don't munge entries with the diff valid VLANs
                    if not old_entry.get('vlan', ''):
                        old_entry['vlan'] = entry['vlan']
                    elif entry['remoteVtepIp']:
                        old_entry['remoteVtepIp'] = entry['remoteVtepIp']
                    if old_entry['remoteVtepIp']:
                        old_entry['flags'] = 'remote'
                    self._add_mackey_protocol(old_entry)
                    drop_indices.append(i)
                    continue
            if 'offload' in entry['flags'] or 'extern_learn' in entry['flags']:
                if entry['remoteVtepIp']:
                    entry['flags'] = 'remote'
            self._add_mackey_protocol(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_sonic_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_junos_data(self, processed_data, _):
        drop_indices = []
        new_entries = []

        for i, entry in enumerate(processed_data):
            if not entry.get('macaddr', ''):
                drop_indices.append(i)
            inflags = entry.pop('flags', '')
            flags = ''
            if inflags:
                if 'rcvd_from_remote' in inflags:
                    flags += ' remote'

            maclist = entry.get('macaddr', '')
            if isinstance(maclist, list):
                # MX format
                oifs = entry.get('oif', [])
                for j, mac in enumerate(maclist):
                    new_entry = entry.copy()
                    new_entry['macaddr'] = mac
                    if not entry['bd']:
                        if '.' in oifs[j]:
                            new_entry['oif'], new_entry['vlan'] = \
                                oifs[j].split('.')
                        else:
                            new_entry['oif'] = oifs[j].split('.')[0]
                    else:
                        new_entry['oif'] = oifs[j]

                    new_entry['flags'] = ''
                    self._add_mackey_protocol(new_entry)
                    new_entries.append(new_entry)
                drop_indices.append(i)
            else:
                entry['flags'] = flags.strip()
                if entry['oif'] and not entry['oif'].startswith('vtep'):
                    entry['oif'] = entry['oif'].split('.')[0]
                self._add_mackey_protocol(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        processed_data.extend(new_entries)
        return processed_data

    def _clean_nxos_data(self, processed_data, _):

        for entry in processed_data:
            entry['macaddr'] = convert_macaddr_format_to_colon(
                entry.get('macaddr', '0000.0000.0000'))
            vtepIP = re.match(r'(\S+)\(([0-9.]+)\)', entry['oif'])
            if vtepIP:
                entry['remoteVtepIp'] = vtepIP.group(2)
                entry['oif'] = vtepIP.group(1)
                entry['flags'] = 'remote'
            else:
                entry['oif'] = expand_nxos_ifname(entry['oif'])
                entry['remoteVtepIp'] = ''

            oif = entry.get('oif', '')
            if oif and '(R)' in oif:
                entry['oif'] = oif.split('(R)')[0]
                entry['flags'] = 'router'

            if entry.get('vlan', '-') == '-':
                entry['vlan'] = 0
            # Handling old NXOS
            if entry.get('_isStatic', 'disabled') == 'enabled':
                entry['flags'] = 'static'
            flags = entry.get('flags').strip()
            if not flags or (flags == '*'):
                entry['flags'] = 'dynamic'

            self._add_mackey_protocol(entry)

        return processed_data

    def _clean_iosxe_data(self, processed_data, _):

        for entry in processed_data:
            entry['macaddr'] = convert_macaddr_format_to_colon(
                entry.get('macaddr', '0000.0000.0000'))
            oiflist = []
            oifs = ''
            oiflist = entry.get('_ports', [])
            for oif in oiflist:
                # Handles multicast entries
                oifs += f'{expand_ios_ifname(oif)} '
            if oifs:
                entry['oif'] = oifs.strip()
            else:
                entry['oif'] = ''

            entry['remoteVtepIp'] = ''
            vlan = entry.get('vlan', ' ').strip()
            if vlan in ["All", "N/A"]:
                entry['vlan'] = 0

            entry['flags'] = entry.get('flags', '').lower()

            self._add_mackey_protocol(entry)

        return processed_data

    def _clean_ios_data(self, processed_data, raw_data):
        return self._clean_iosxe_data(processed_data, raw_data)

    def _clean_eos_data(self, processed_data, _):

        drop_indices = []

        for i, entry in enumerate(processed_data):
            entry['oif'] = expand_eos_ifname(entry['oif'])
            if (entry['oif'].startswith('Vxlan') and
                    'remoteVtepIp' not in entry):
                drop_indices.append(i)
                continue
            if '.' in entry['macaddr']:
                entry['macaddr'] = convert_macaddr_format_to_colon(
                    entry.get('macaddr', '0000.0000.0000'))
            self._add_mackey_protocol(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data
