from suzieq.poller.services.service import Service
import numpy as np


class RoutesService(Service):
    """routes service. Different class because vrf default needs to be added"""

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, run_once="forever"):

        super().__init__(name, defn, period, stype, keys, ignore_fields, schema,
                         queue, run_once)
        # Change the partition columns to not include the prefix
        # We don't want millions of directories, one per prefix
        self.partition_cols.remove("prefix")

    def _fix_ipvers(self, entry):
        if ':' in entry['prefix']:
            entry['ipvers'] = 6
        else:
            entry['ipvers'] = 4

    def _common_data_cleaner(self, processed_data, raw_data):
        for entry in processed_data:
            self._fix_ipvers(entry)

        return processed_data

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

        for i, entry in enumerate(processed_data):
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

            if entry['_localif']:
                entry['oifs'] = [entry['_localif']]

            entry['protocol'] = entry['protocol'].lower()
            if entry['_rtlen'] != 0:
                drop_entries_idx.append(i)

            entry['active'] = entry['_activeTag'] == '*'

            entry['metric'] = int(entry['metric'])
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

            entry['weights'] = [int(x) if x is not None else 0
                                for x in entry['weights']]
            oiflist = []
            for oif in entry['oifs']:
                if oif:
                    if 'Eth' in oif:
                        oif = oif.replace('Eth', 'Ethernet')
                    oiflist.append(oif)
            entry['oifs'] = oiflist

            if not entry['oifs']:
                oiflist = []
                for nhv in entry.get('_nexthopVrf', []):
                    if nhv:
                        oiflist.append(f'_nexthopVrf:{nhv}')
                entry['oifs'] = oiflist

            self._fix_ipvers(entry)
            if 'action' not in entry:
                entry['action'] = 'forward'

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data
