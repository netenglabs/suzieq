from suzieq.poller.services.service import Service
import re
import numpy as np
from suzieq.utils import convert_macaddr_format_to_colon


class ArpndService(Service):
    """arpnd service. Different class because minor munging of output"""

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, run_once="forever"):

        super().__init__(name, defn, period, stype, keys, ignore_fields, schema,
                         queue, run_once)
        # Change the partition columns to not include the IPAddress
        # We don't want millions of directories, one per prefix
        self.partition_cols.remove("ipAddress")

    def _common_data_cleaner(self, processed_data, raw_data):
        for entry in processed_data:
            entry['oif'] = entry['oif'].replace('/', '-')

        return processed_data

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["remote"] = entry["remote"] == "offload"
            entry["state"] = entry["state"].lower()
            if entry["state"] == "stale" or entry["state"] == "delay":
                entry["state"] = "reachable"
            entry['origIfname'] = entry['oif']
            if not entry.get('macaddr', None):
                entry['macaddr'] = '00:00:00:00:00:00'
        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_eos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry['macaddr'] = convert_macaddr_format_to_colon(
                entry.get('macaddr', '0000.0000.0000'))
            if ',' in entry['oif']:
                entry['oif'] = entry['oif'].split(',')[0].strip()
                entry['origIfname'] = entry['oif']
            entry['oif'] = entry['oif'].replace('/', '-')

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        for entry in processed_data:
            if '[vtep.' in entry['oif']:
                entry['remote'] = True
            if entry['oif']:
                entry['oif'] = re.sub(r' \[.*\]', '', entry['oif'])
                entry['oif'] = entry['oif'].replace('/', '-')
            entry['state'] = 'reachable'
            if not entry.get('macaddr', None):
                entry['macaddr'] = '00:00:00:00:00:00'

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):

        drop_indices = []
        for i, entry in enumerate(processed_data):
            if not entry['ipAddress']:
                drop_indices.append(i)
                continue
            if entry['oif']:
                entry['oif'] = entry['oif'].replace('/', '-')
            entry['macaddr'] = convert_macaddr_format_to_colon(
                entry.get('macaddr', '0000.0000.0000'))

        processed_data = np.delete(processed_data,
                                   drop_indices).tolist()
        return processed_data
