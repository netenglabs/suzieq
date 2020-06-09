from suzieq.poller.services.service import Service


class LldpService(Service):
    """LLDP service. Different class because of munging ifname"""

    def clean_data(self, processed_data, raw_data):

        for entry in processed_data:
            if not entry:
                continue
            entry['ifname'] = entry['ifname'].replace('/', '-')
            if entry.get('subtype', None) == 'Mac address':
                entry['peerIfname'] = '-'
            else:
                entry['peerMacaddr'] = '00:00:00:00:00:00'
        return super().clean_data(processed_data, raw_data)
