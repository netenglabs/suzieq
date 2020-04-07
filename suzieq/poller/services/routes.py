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
        if any([devtype == x for x in ["cumulus", "linux"]]):
            for entry in processed_data:
                entry["vrf"] = entry["vrf"] or "default"
                entry["metric"] = entry["metric"] or 20
                for ele in ["nexthopIps", "oifs"]:
                    entry[ele] = entry[ele] or [""]
                entry["weights"] = entry["weights"] or [1]
                if entry['prefix'] == 'default':
                    if any(':' in x for x in entry['nexthopIps']):
                        entry['prefix'] = '::0/0'
                    else:
                        entry['prefix'] = '0.0.0.0/0'
                if '/' not in entry['prefix']:
                    entry['prefix'] += '/32'
                if not entry["action"]:
                    entry["action"] = "forward"
                elif entry["action"] == "blackhole":
                    entry["oifs"] = ["blackhole"]
                if ':' in entry['prefix']:
                    entry['ipvers'] = 6
                else:
                    entry['ipvers'] = 4

                entry['inHardware'] = True  # Till the offload flag is here

        return super().clean_data(processed_data, raw_data)
