from suzieq.poller.services.service import Service
import re
from suzieq.utils import convert_macaddr_format_to_colon


class MacsService(Service):
    """Mac address service. Different class because of macaddr not in key"""

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, run_once="forever"):

        super().__init__(name, defn, period, stype, keys, ignore_fields, schema,
                         queue, run_once)
        # Change the partition columns to not include the prefix
        # We don't want millions of directories, one per prefix
        self.partition_cols.remove("macaddr")

    def get_key_flds(self):
        """The MAC table in Linux can have weird keys"""
        return ['vlan', 'macaddr', 'oif', 'remoteVtepIp', 'bd']

    def _add_mackey_protocol(self, entry):
        if not entry.get("vlan", 0):
            # Without a VLAN, make the OIF the key
            if not entry.get("remoteVtepIp", None):
                if not entry.get("bd", None):
                    entry['protocol'] = 'l2'
                    entry["mackey"] = entry["oif"]
                else:
                    entry['protocol'] = 'vpls'
                    entry["mackey"] = entry["bd"]
            else:
                entry['protocol'] = 'vxlan'
                entry["mackey"] = f'{entry["oif"]}-{entry["remoteVtepIp"]}'
        else:
            if not entry.get("bd", None):
                entry['protocol'] = 'l2'
                entry["mackey"] = entry["vlan"]
            else:
                entry['protocol'] = 'vpls'
                entry["mackey"] = f'{entry["bd"]}-{entry["vlan"]}'

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            if entry['flags'] == 'offload' or entry['flags'] == 'extern_learn':
                if entry['remoteVtepIp']:
                    entry['flags'] = 'remote'
            self._add_mackey_protocol(entry)

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
            self._add_mackey_protocol(entry)

        return processed_data

    def _clean_eos_data(self, processed_data, raw_data):

        for entry in processed_data:
            entry['macaddr'] = convert_macaddr_format_to_colon(
                entry.get('macaddr', '0000.0000.0000'))
            vtepIP = re.match(r'(\S+)\(([0-9.]+)\)', entry['oif'])
            if vtepIP:
                entry['remoteVtepIp'] = vtepIP.group(2)
                entry['oif'] = vtepIP.group(1)
                entry['flags'] = 'remote'
            self._add_mackey_protocol(entry)

        return processed_data
