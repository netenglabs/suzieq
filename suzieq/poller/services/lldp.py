from suzieq.poller.services.service import Service


class LldpService(Service):
    """LLDP service. Different class because of munging ifname"""

    def clean_data(self, processed_data, raw_data):

        for entry in processed_data:
            entry['ifname'] = entry['ifname'].replace('/', '-')
            if entry['subtype'] == 'Mac address':
                entry['peerIfname'] = '-'
            else:
                entry['peerMacaddr'] = '00:00:00:00:00:00'
        return super().clean_data(processed_data, raw_data)
