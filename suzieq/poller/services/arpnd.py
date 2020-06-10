from suzieq.poller.services.service import Service


class ArpndService(Service):
    """arpnd service. Different class because minor munging of output"""

    def clean_data(self, processed_data, raw_data):

        devtype = self._get_devtype_from_input(raw_data)

        if any([devtype == x for x in ["cumulus", "linux"]]):
            for entry in processed_data:
                entry["offload"] = entry["offload"] == "offload"
                entry["state"] = entry["state"].lower()
                if entry["state"] == "stale" or entry["state"] == "delay":
                    entry["state"] = "reachable"
                entry['oif'] = entry['oif'].replace('/', '-')
        elif devtype == 'eos':
            for entry in processed_data:
                entry['macaddr'] = ':'.join(
                    [f'{x[:2]}:{x[2:]}' for x in entry['macaddr'].split('.')])
                entry['ifname'] = entry['ifname'].replace('/', '-')
        else:
            for entry in processed_data:
                entry['oif'] = entry['oif'].replace('/', '-')

        return super().clean_data(processed_data, raw_data)
