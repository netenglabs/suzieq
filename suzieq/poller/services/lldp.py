from suzieq.poller.services.service import Service
from suzieq.utils import convert_macaddr_format_to_colon, expand_ios_ifname
import re
import numpy as np


class LldpService(Service):
    """LLDP service. Different class because of munging ifname"""

    def _common_data_cleaner(self, processed_data, raw_data):

        for i, entry in enumerate(processed_data):
            if not entry:
                continue
            self._common_cleaner(entry)

        return processed_data

    def _common_cleaner(self, entry):
        if entry.get('_chassisType', '') == 'Mac address':
            entry['peerHostname'] = convert_macaddr_format_to_colon(
                entry.get('peerHostname', '0000.0000.0000'))

        entry['subtype'] = entry.get('subtype', '').lower()
        subtype = entry.get('subtype', '')
        if subtype in ["interface name", '']:
            entry['peerMacaddr'] = '00:00:00:00:00:00'
            entry['peerIfindex'] = 0
            entry['subtype'] = 'interface name'  # IOS* don't provide subtype
        if subtype == 'mac address':
            entry['peerMacaddr'] = convert_macaddr_format_to_colon(
                entry.get('peerIfname', '0000.0000.0000'))
            entry['peerIfname'] = '-'
            entry['peerIfindex'] = 0
        elif subtype.startswith('locally'):
            entry['peerIfindex'] = entry['peerIfname']
            entry['peerIfname'] = '-'
            entry['peerMacaddr'] = '00:00:00:00:00:00'

    def _clean_nxos_data(self, processed_data, raw_data):

        drop_indices = []
        entries = {}

        for i, entry in enumerate(processed_data):
            entry['peerHostname'] = re.sub(r'\(.*\)', '',
                                           entry['peerHostname'])
            entry['ifname'] = re.sub(
                r'^Eth?(\d)', 'Ethernet\g<1>', entry['ifname'])

            if entry['ifname'] in entries:
                # Description is sometimes filled in with CDP, but not LLDP
                if not entry.get('description', ''):
                    old_entry = processed_data[entries[entry['ifname']]]
                    entry['description'] = old_entry.get('description', '')
                    drop_indices.append(entries[entry['ifname']])
            else:
                entries[entry['ifname']] = i

            if entry.get('protocol', '') == 'cdp':
                entry['subtype'] = 'interface name'

            entry['peerIfname'] = expand_ios_ifname(
                entry.get('peerIfname', ''))

            if entry.get('mgmtIP', '') == "not advertised":
                entry['mgmtIP'] = ''  # make it consistent with other NOS
            self._common_cleaner(entry)
            if not entry['peerHostname']:
                drop_indices.append(i)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        for entry in processed_data:
            self._common_cleaner(entry)
        return processed_data

    def _clean_eos_data(self, processed_data, raw_data):

        drop_indices = []

        for i, entry in enumerate(processed_data):
            subtype = entry.get('subtype', '')
            if subtype == 'interfaceName':
                entry['subtype'] = 'interface name'
            elif subtype == 'macAddress':
                entry['subtype'] = 'mac address'
            elif subtype == "local":
                entry['subtype'] = 'locally assigned'

            self._common_cleaner(entry)
            if not entry['peerHostname']:
                drop_indices.append(i)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        for entry in processed_data:
            subtype = entry.get('subtype', '')
            if subtype == "ifname":
                entry['subtype'] = "interface name"
            elif subtype == "local":
                entry['subtype'] = "locally assigned"

            self._common_cleaner(entry)

        return processed_data

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            subtype = entry.get('subtype', '')
            if subtype == 'ifname':
                entry['subtype'] = 'interface name'
            elif subtype == 'local':
                entry['subtype'] = 'locally assigned'
            elif subtype == 'mac':
                entry['subtype'] = 'mac address'
            self._common_cleaner(entry)

        return processed_data

    def _clean_iosxr_data(self, processed_data, raw_data):
        for entry in processed_data:
            self._common_cleaner(entry)
        return processed_data

    def _clean_iosxe_data(self, processed_data, raw_data):
        for entry in processed_data:
            for field in ['ifname', 'peerIfname']:
                entry[field] = expand_ios_ifname(entry[field])
                if ' ' in entry.get(field, ''):
                    entry[field] = entry[field].replace(' ', '')
            self._common_cleaner(entry)

        return processed_data

    def _clean_ios_data(self, processed_data, raw_data):
        return self._clean_iosxe_data(processed_data, raw_data)

    def _clean_sonic_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)
