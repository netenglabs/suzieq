from suzieq.poller.services.service import Service
from suzieq.utils import convert_macaddr_format_to_colon
import re


class LldpService(Service):
    """LLDP service. Different class because of munging ifname"""

    def get_key_flds(self):
        """The MAC table in Linux can have weird keys"""
        return ['ifname', 'peerHostname', 'peerIfname']

    def _common_data_cleaner(self, processed_data, raw_data):

        devtype = self._get_devtype_from_input(raw_data)

        for i, entry in enumerate(processed_data):
            if not entry:
                continue
            if entry.get('_chassisType', '') == 'Mac Address':
                entry['peerHostname'] = convert_macaddr_format_to_colon(
                    entry.get('peerHostname', '0000.0000.0000'))
            if 'peerIfname' in entry:
                subtype = entry.get('subtype', '')
                if subtype == 'Mac Address':
                    entry['subtype'] = 'macddress'
                    entry['peerMacaddr'] = convert_macaddr_format_to_colon(
                        entry.get('peerIfname', '0000.0000.0000'))
                    entry['peerIfname'] = '-'
                    entry['peerIfindex'] = 0
                elif subtype == 'ifindex':
                    entry['subtype'] = 'ifindex'
                    entry['peerIfname'] = '-'
                    entry['peerMacaddr'] = '00:00:00:00:00:00'
                else:
                    entry['subtype'] = 'ifname'
                    entry['peerMacaddr'] = '00:00:00:00:00:00'
                    entry['peerIfindex'] = 0

            if devtype == 'nxos':
                entry['peerHostname'] = re.sub(r'\(.*\)', '',
                                               entry['peerHostname'])
                entry['ifname'] = re.sub(
                    r'^Eth?(\d)', 'Ethernet\g<1>', entry['ifname'])

        return processed_data
