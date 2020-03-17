from suzieq.poller.services.service import Service


class RoutesService(Service):
    """routes service. Different class because vrf default needs to be added"""

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, run_once="forever"):

        super().__init__(name, defn, period, stype, keys, ignore_fields, schema,
                         queue, run_once)
        # Change the partition columns to not include the prefix
        # We don't want millions of directories, one per prefix
        self.partition_cols.remove("prefix")

    def clean_data(self, processed_data, raw_data):

        devtype = raw_data.get("devtype", None)
        if any([devtype == x for x in ["cumulus", "linux", "platina"]]):
            for entry in processed_data:
                entry["vrf"] = entry["vrf"] or "default"
                entry["metric"] = entry["metric"] or 20
                for ele in ["nexthopIps", "oifs"]:
                    entry[ele] = entry[ele] or [""]
                entry["weights"] = entry["weights"] or [1]
                if entry['prefix'] == 'default':
                    entry['prefix'] = '0.0.0.0/0'

        return super().clean_data(processed_data, raw_data)
