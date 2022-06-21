import re

import numpy as np

from suzieq.poller.worker.services.service import Service
from suzieq.shared.utils import (convert_macaddr_format_to_colon,
                                 expand_ios_ifname, expand_nxos_ifname)


class LldpService(Service):
    """LLDP service. Different class because of munging ifname"""

    def _common_data_cleaner(self, processed_data, _):

        drop_indices = []

        for i, entry in enumerate(processed_data):

            if not entry:
                continue

            if not entry.get('ifname', ''):
                drop_indices.append(i)
                continue

            self._common_cleaner(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _common_cleaner(self, entry):
        chassis_type = entry.get('_chassisType', '')
        if not isinstance(chassis_type, str):
            if chassis_type == 7:
                chassis_type = 'peerHostname'
            else:
                chassis_type = 'unknown'
        chassis_type = chassis_type.lower()
        if chassis_type == 'mac address':
            entry['peerHostname'] = convert_macaddr_format_to_colon(
                entry.get('peerHostname', '0000.0000.0000'))

        subtype = str(entry.get('subtype', '')).lower()
        if subtype in ["interface name", '', '5', '7']:
            entry['peerMacaddr'] = '00:00:00:00:00:00'
            entry['peerIfindex'] = 0
            entry['subtype'] = 'interface name'  # IOS* don't provide subtype
        if subtype == 'mac address':
            entry['peerMacaddr'] = convert_macaddr_format_to_colon(
                entry.get('peerIfname', '0000.0000.0000'))
            entry['peerIfname'] = '-'
            entry['peerIfindex'] = 0
            entry['subtype'] = 'mac address'
        elif subtype.startswith(('locally', '1')):
            if not entry['peerIfname'].isnumeric():
                # lldpd assigns ifname, but calls it locally assigned
                entry['subtype'] = 'interface name'
                entry['peerIfindex'] = 0
                entry['peerMacaddr'] = '00:00:00:00:00:00'
            else:
                entry['peerIfindex'] = entry['peerIfname']
                entry['peerIfname'] = '-'
                entry['peerMacaddr'] = '00:00:00:00:00:00'
                entry['subtype'] = 'locally assigned'

    def _clean_nxos_data(self, processed_data, _):

        drop_indices = []
        entries = {}

        for i, entry in enumerate(processed_data):
            entry['peerHostname'] = re.sub(r'\(.*\)', '',
                                           entry['peerHostname'])
            if not entry.get('ifname', ''):
                # This is a case where NXOS version 7.0.7 has a bug with longer
                # hostnames where it squishes the hostname and ifname into a
                # single string without even a single space between them.
                val = entry.get('peerHostname', '')
                res = val.split('mgmt')
                if len(res) == 2:
                    entry['peerHostname'] = res[0]
                    entry['ifname'] = f'mgmt{res[1]}'
                elif '/' in val:  # hostnames can't have / as per standards
                    res = val.split('Eth')
                    if len(res) == 2:
                        entry['peerHostname'] = res[0]
                        entry['ifname'] = f'Eth{res[1]}'

            entry['ifname'] = expand_nxos_ifname(entry['ifname'])

            if entry['ifname'] in entries:
                # Description is sometimes filled in with CDP, but not LLDP
                if not entry.get('description', ''):
                    old_entry = processed_data[entries[entry['ifname']]]
                    entry['description'] = old_entry.get('description', '')
                    entry['subtype'] = old_entry.get('subtype', '')
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

    def _clean_junos_data(self, processed_data, _):

        drop_indices = []
        for i, entry in enumerate(processed_data):
            if not entry.get('ifname', ''):
                drop_indices.append(i)
                continue

            self._common_cleaner(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_eos_data(self, processed_data, _):

        drop_indices = []

        for i, entry in enumerate(processed_data):
            if not entry['ifname']:
                drop_indices.append(i)

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

    def _clean_cumulus_data(self, processed_data, _):

        drop_indices = []

        for i, entry in enumerate(processed_data):
            if not entry['ifname']:
                drop_indices.append(i)
            subtype = entry.get('subtype', '')
            if subtype == "ifname":
                entry['subtype'] = "interface name"
            elif subtype == "local":
                entry['subtype'] = "locally assigned"

            self._common_cleaner(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_linux_data(self, processed_data, _):

        drop_indices = []
        for i, entry in enumerate(processed_data):
            if not entry['ifname']:
                drop_indices.append(i)
                continue
            entry['ifname'] = entry['ifname'].replace(' ', '')
            entry['peerIfname'] = entry['peerIfname'].replace(' ', '')
            subtype = entry.get('subtype', '')
            if subtype == 'ifname':
                entry['subtype'] = 'interface name'
            elif subtype == 'local':
                entry['subtype'] = 'locally assigned'
            elif subtype == 'mac':
                entry['subtype'] = 'mac address'
            self._common_cleaner(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_iosxr_data(self, processed_data, _):

        drop_indices = []
        for i, entry in enumerate(processed_data):
            if not entry['ifname']:
                drop_indices.append(i)
            self._common_cleaner(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_iosxe_data(self, processed_data, _):

        drop_indices = []
        for i, entry in enumerate(processed_data):
            entry['peerHostname'] = re.sub(r'\(.*\)', '',
                                           entry['peerHostname'])
            if not entry['ifname']:
                drop_indices.append(i)

            # IOS can have the last 2 columns of its output as either
            # Gig 0/1/2 or N5K Gig 0/1/2 or N5K mgmt0. In this last
            # case we accidentally assume N5kmgmt0 as the peer interface
            # name. The following code tries to fix that.
            pif = entry.get('peerIfname', '')
            if pif:
                words = pif.split()
                if words[-1] == "mgmt0":
                    entry['peerIfname'] = "mgmt0"
            for field in ['ifname', 'peerIfname']:
                entry[field] = expand_ios_ifname(entry[field])
                if ' ' in entry.get(field, ''):
                    entry[field] = entry[field].replace(' ', '')
            self._common_cleaner(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_ios_data(self, processed_data, raw_data):
        return self._clean_iosxe_data(processed_data, raw_data)

    def _clean_sonic_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_panos_data(self, processed_data, _):
        for entry in processed_data:
            entry["subtype"] = entry["subtype"].lower()

            self._common_cleaner(entry)
        return processed_data
