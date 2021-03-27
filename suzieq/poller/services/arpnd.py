from suzieq.poller.services.service import Service
import re
import numpy as np
from suzieq.utils import (convert_macaddr_format_to_colon,
                          iosxr_get_full_ifname)


class ArpndService(Service):
    """arpnd service. Different class because minor munging of output"""

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["remote"] = entry["remote"] == "offload"
            entry["state"] = entry["state"].lower()
            if entry["state"] == "stale" or entry["state"] == "delay":
                entry["state"] = "reachable"
            elif entry['state'] in ['extern_learn', 'offload']:
                entry['state'] = 'reachable'
                entry['remote'] = True
            if not entry.get('macaddr', None):
                entry['macaddr'] = '00:00:00:00:00:00'
        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_eos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry['macaddr'] = convert_macaddr_format_to_colon(
                entry.get('macaddr', '0000.0000.0000'))
            # EOS has entries with OIF of type: "Vlan4094, Port-Channel1"
            # We need only the first part, we pick up the second from the
            # MAC table
            if ',' in entry['oif']:
                ports = entry['oif'].split(',')
                entry['oif'] = ports[0].strip()
                if ports[1].strip() == 'Vxlan1':
                    entry['remote'] = True

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        for entry in processed_data:
            if '[vtep.' in entry['oif']:
                entry['remote'] = True
            if entry['oif']:
                entry['oif'] = re.sub(r' \[.*\]', '', entry['oif'])
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

            if entry['macaddr'] is None:
                entry['state'] = "failed"
                entry['macaddr'] = '00:00:00:00:00:00'
            else:
                entry['macaddr'] = convert_macaddr_format_to_colon(
                    entry.get('macaddr', '0000.0000.0000'))

        processed_data = np.delete(processed_data,
                                   drop_indices).tolist()
        return processed_data

    def _clean_iosxr_data(self, processed_data, raw_data):

        for entry in processed_data:
            if entry['macaddr'] is None:
                entry['state'] = "failed"
                entry['macaddr'] = '00:00:00:00:00:00'
            else:
                entry['macaddr'] = convert_macaddr_format_to_colon(
                    entry.get('macaddr', '0000.0000.0000'))
                entry['state'] = "reachable"
            if ':' in entry['ipAddress']:
                # We need to fix up the interface name for IPv6 ND entriie
                entry['oif'] = iosxr_get_full_ifname(entry.get('oif', ''))

        return processed_data
