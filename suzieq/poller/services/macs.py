from suzieq.poller.services.service import Service
import re


class MacsService(Service):
    """Mac address service. Different class because of macaddr not in key"""

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, run_once="forever"):

        super().__init__(name, defn, period, stype, keys, ignore_fields, schema,
                         queue, run_once)
        # Change the partition columns to not include the prefix
        # We don't want millions of directories, one per prefix
        self.partition_cols.remove("macaddr")

    def _add_mackey(self, entry):
        if not entry["vlan"]:
            # Without a VLAN, make the OIF the key
            if not entry["remoteVtepIp"]:
                entry["mackey"] = entry["oif"]
            else:
                entry["mackey"] = f'{entry["oif"]}/{entry["remoteVtepIp"]}'
        else:
            entry["mackey"] = entry["vlan"]

    def clean_data(self, processed_data, raw_data):
        """CLeanup needed for the messed up MAC table entries in Linux"""

        devtype = self._get_devtype_from_input(raw_data)
        if any([devtype == x for x in ["cumulus", "linux"]]):
            processed_data = self._clean_linux_data(processed_data, raw_data)
        elif devtype == "junos":
            processed_data = self._clean_junos_data(processed_data, raw_data)
        elif devtype == "nxos":
            processed_data = self._clean_nxos_data(processed_data, raw_data)
        return super().clean_data(processed_data, raw_data)

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            if entry['flags'] == 'offload' or entry['flags'] == 'extern_learn':
                if entry['remoteVtepIp']:
                    entry['flags'] = 'remote'
            self._add_mackey(entry)

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        for entry in processed_data:
            inflags = entry.pop('flags', '')
            flags = ''
            if inflags:
                if 'rcvd_from_remote' in inflags:
                    flags += ' remote'
            entry['flags'] = flags.strip()
            self._add_mackey(entry)

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):

        for entry in processed_data:
            entry['macaddr'] = ':'.join(
                [f'{x[:2]}:{x[2:]}' for x in entry['macaddr'].split('.')])
            vtepIP = re.match(r'(\S+)\(([0-9.]+)\)', entry['oif'])
            if vtepIP:
                entry['remoteVtepIp'] = vtepIP.group(2)
                entry['oif'] = vtepIP.group(1)
                entry['flags'] = 'remote'
            self._add_mackey(entry)

        return processed_data
