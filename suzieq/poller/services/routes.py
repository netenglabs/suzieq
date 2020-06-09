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
            processed_data = self._clean_linux_data(processed_data, raw_data)
        elif devtype == "junos":
            processed_data = self._clean_junos_data(processed_data, raw_data)
        elif devtype == "nxos":
            processed_data = self._clean_nxos_data(processed_data, raw_data)
        else:
            # Fix IP version for all entries
            for entry in processed_data:
                if ':' in entry['prefix']:
                    entry['ipvers'] = 6
                else:
                    entry['ipvers'] = 4

        return super().clean_data(processed_data, raw_data)

    def _clean_linux_data(self, processed_data, raw_data):
        """Clean Linux ip route data"""
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

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        """Clean VRF name in JUNOS data"""

        for entry in processed_data:
            vrf = entry.pop("vrf")[0]['data']
            if vrf == "inet.0":
                vrf = "default"
                vers = 4
            elif vrf == "inet6.0":
                vrf = "default"
                vers = 6
            else:
                vrf, family, _ = vrf.split('.')
                if family == "inet":
                    vers = 4
                elif family == "inet6":
                    vers = 6
            entry['vrf'] = vrf
            entry['ipvers'] = vers

            if entry['localif']:
                entry['oifs'] = [entry['localif']]

            entry['protocol'] = entry['protocol'].lower()
            if entry['activeTag'] == '*':
                entry['active'] = True
            else:
                entry['active'] = False

            entry['metric'] = int(entry['metric'])
            entry.pop('localif')
            entry.pop('activeTag')

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):

        for entry in processed_data:
            entry['protocol'] = entry['protocol'].split('-')[0]

            entry['weights'] = [int(x) if x is not None else 0
                                for x in entry['weights']]

        return processed_data
