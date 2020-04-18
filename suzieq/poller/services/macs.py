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
            return self._clean_linux_data(processed_data, raw_data)
        return super().clean_data(processed_data, raw_data)

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            if not entry["vlan"]:
                # Without a VLAN, make the OIF the key
                entry["mackey"] = entry["oif"]
            else:
                entry["mackey"] = entry["vlan"]

        return super().clean_data(processed_data, raw_data)
