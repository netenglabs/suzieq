from suzieq.poller.services.service import Service
import re


class LldpService(Service):
    """LLDP service. Different class because of munging ifname"""

    def get_key_flds(self):
        """The MAC table in Linux can have weird keys"""
        return ['ifname', 'peerHostname', 'peerIfname']

    def _common_data_cleaner(self, processed_data, raw_data):

        devtype = self._get_devtype_from_input(raw_data)

        for entry in processed_data:
            if not entry:
                continue
            if 'peerIfname' in entry:
                entry['subtype'] = 'ifname'
                entry['peerMacaddr'] = '00:00:00:00:00:00'
                entry['peerIfindex'] = 0
            elif 'peerMacaddr' in entry:
                entry['subtype'] = 'macddress'
                entry['peerIfname'] = '-'
                entry['peerIfindex'] = 0
            elif 'peerIfindex' in entry:
                entry['subtype'] = 'ifindex'
                entry['peerIfname'] = '-'
                entry['peerMacaddr'] = '00:00:00:00:00:00'

            if devtype == 'nxos':
                entry['peerHostname'] = re.sub(r'\(.*\)', '',
                                               entry['peerHostname'])
                entry['ifname'] = re.sub(
                    r'^Eth?(\d)', 'Ethernet\g<1>', entry['ifname'])

        return processed_data
