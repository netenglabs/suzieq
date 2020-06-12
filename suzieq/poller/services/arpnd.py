from suzieq.poller.services.service import Service
import re


class ArpndService(Service):
    """arpnd service. Different class because minor munging of output"""

    def clean_data(self, processed_data, raw_data):

        devtype = self._get_devtype_from_input(raw_data)

        if any([devtype == x for x in ["cumulus", "linux"]]):
            processed_data = self._clean_linux_data(processed_data, raw_data)
        elif devtype == 'eos':
            processed_data = self._clean_eos_data(processed_data, raw_data)
        elif devtype == 'junos':
            processed_data = self._clean_junos_data(processed_data, raw_data)
        else:
            for entry in processed_data:
                entry['oif'] = entry['oif'].replace('/', '-')

        return super().clean_data(processed_data, raw_data)

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["remote"] = entry["remote"] == "offload"
            entry["state"] = entry["state"].lower()
            if entry["state"] == "stale" or entry["state"] == "delay":
                entry["state"] = "reachable"
            entry['oif'] = entry['oif'].replace('/', '-')

        return processed_data

    def _clean_eos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry['macaddr'] = ':'.join(
                [f'{x[:2]}:{x[2:]}' for x in entry['macaddr'].split('.')])
            entry['ifname'] = entry['ifname'].replace('/', '-')

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry['oif'] = entry['oif'].replace('/', '-')
            if '[vtep.' in entry['oif']:
                entry['remote'] = True
            entry['oif'] = re.sub(r' \[vtep\.\d+\]', '', entry['oif'])
            entry['state'] = 'reachable'

        return processed_data
