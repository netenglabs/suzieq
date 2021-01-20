from suzieq.poller.services.service import Service
import re
from suzieq.utils import convert_macaddr_format_to_colon
from suzieq.utils import expand_nxos_ifname, expand_eos_ifname
import numpy as np


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
        if entry.get('vlan', ''):
            entry['vlan'] = int(entry['vlan'])

        if entry.get('bd', ""):
            # VPLS Entry
            if not entry.get('vlan', 0):
                entry['mackey'] = entry['bd']
            else:
                entry['mackey'] = f'{entry["bd"]}-{entry["vlan"]}'
        else:
            if not entry.get("remoteVtepIp", ''):
                if entry['macaddr'] == '00:00:00:00:00:00':
                    entry['mackey'] = f'{entry["vlan"]}-{entry["remoteVtepIp"]}'
                else:
                    entry['mackey'] = entry['vlan']
            else:
                if entry.get('vlan', 0):
                    entry['mackey'] = entry['vlan']
                else:
                    entry['mackey'] = f'{entry["vlan"]}-{entry["oif"]}'

    def _clean_linux_data(self, processed_data, raw_data):
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
                    else:
                        old_entry['remoteVtepIp'] = entry['remoteVtepIp']
                    old_entry['flags'] = 'remote'
                    self._add_mackey_protocol(old_entry)
                    drop_indices.append(i)
                    continue
            if entry['flags'] == 'offload' or entry['flags'] == 'extern_learn':
                if entry['remoteVtepIp']:
                    entry['flags'] = 'remote'
            self._add_mackey_protocol(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_junos_data(self, processed_data, raw_data):
        for entry in processed_data:
            inflags = entry.pop('flags', '')
            flags = ''
            if inflags:
                if 'rcvd_from_remote' in inflags:
                    flags += ' remote'

            if entry.get('bd', None):
                entry['protocol'] = 'vpls'
                flags = inflags + ' remote'
            entry['flags'] = flags.strip()
            self._add_mackey_protocol(entry)

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):

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
            if entry.get('vlan', '-') == '-':
                entry['vlan'] = 0
            self._add_mackey_protocol(entry)

        return processed_data

    def _clean_eos_data(self, processed_data, raw_data):

        foo = 0
        for entry in processed_data:
            if '.' in entry['macaddr']:
                entry['macaddr'] = convert_macaddr_format_to_colon(
                    entry.get('macaddr', '0000.0000.0000'))
            entry['oif'] = expand_eos_ifname(entry['oif'])
            self._add_mackey_protocol(entry)

        return processed_data
