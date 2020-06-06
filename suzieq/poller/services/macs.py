from suzieq.poller.services.service import Service


class MacsService(Service):
    """Mac address service. Different class because of macaddr not in key"""

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, run_once="forever"):

        super().__init__(name, defn, period, stype, keys, ignore_fields, schema,
                         queue, run_once)
        # Change the partition columns to not include the prefix
        # We don't want millions of directories, one per prefix
        self.partition_cols.remove("macaddr")

    def clean_data(self, processed_data, raw_data):
        """CLeanup needed for the messed up MAC table entries in Linux"""
        devtype = raw_data.get("devtype", None)
        if any([devtype == x for x in ["cumulus", "linux"]]):
            processed_data = self._clean_linux_data(processed_data, raw_data)
        elif devtype == "junos":
            processed_data = self._clean_junos_data(processed_data, raw_data)
        return super().clean_data(processed_data, raw_data)

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            if not entry["vlan"]:
                # Without a VLAN, make the OIF the key
                if not entry["remoteVtepIp"]:
                    entry["mackey"] = entry["oif"]
                else:
                    entry["mackey"] = f'{entry["oif"]}/{entry["remoteVtepIp"]}'
            else:
                entry["mackey"] = entry["vlan"]

            if entry['flags'] == 'offload' or entry['flags'] == 'extern_learn':
                if entry['remoteVtepIp']:
                    entry['flags'] = 'remote'

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        for entry in processed_data:
            if not entry["vlan"]:
                # Without a VLAN, make the OIF the key
                if not entry["remoteVtepIp"]:
                    entry["mackey"] = entry["oif"]
                else:
                    entry["mackey"] = f'{entry["oif"]}/{entry["remoteVtepIp"]}'
            else:
                entry["mackey"] = entry["vlan"]

            inflags = entry.pop('flags', '')
            flags = ''
            if inflags:
                if 'rcvd_from_remote' in inflags:
                    flags += ' remote'
            entry['flags'] = flags.strip()

        return processed_data
