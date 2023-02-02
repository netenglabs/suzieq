import numpy as np
from suzieq.shared.utils import expand_ios_ifname, expand_nxos_ifname
from suzieq.poller.worker.services.service import Service


class VlanService(Service):
    """Vlan service. Different class because Vlan is not right type for EOS"""

    def clean_json_input(self, data):
        """evpnVni JSON output is busted across many NOS. Fix it"""

        devtype = data.get("devtype", None)
        if devtype == 'junos-mx':
            data['data'] = data['data'].replace('}, \n    }\n', '} \n    }\n')

        return data['data']

    def _clean_eos_data(self, processed_data, _):
        '''Massage the interface output'''

        for entry in processed_data:
            if (entry['vlanName'].startswith('VLAN') or
                    entry['vlanName'] == "default"):
                entry['vlanName'] = f'vlan{entry["vlan"]}'

        return processed_data

    def _clean_cumulus_data(self, processed_data, _):
        '''Fix Linux VLAN output.
        Linux output is the transposed from the vlan output of all other NOS
        '''

        new_entries = []
        entry_dict = {}

        for entry in processed_data:

            for item in entry['vlan']:
                vlan = int(item)
                vlanName = f'vlan{vlan}'

                if entry['vlanName'] == 'bridge':
                    state = 'suspended'
                else:
                    state = 'active'
                if vlanName not in entry_dict:
                    new_entry = {'vlanName': vlanName,
                                 'state': state,
                                 'vlan': vlan,
                                 'interfaces': set(),
                                 }
                    new_entries.append(new_entry)
                    entry_dict[vlanName] = new_entry
                else:
                    new_entry = entry_dict[vlanName]

                if entry['vlanName'] != 'bridge':
                    new_entry['interfaces'].add(entry['vlanName'])
                    new_entry['state'] = 'active'

        for entry in new_entries:
            entry['interfaces'] = list(entry['interfaces'])

        return new_entries

    def _clean_sonic_data(self, processed_data, raw_data):
        return self._clean_cumulus_data(processed_data, raw_data)

    def _clean_nxos_data(self, processed_data, _):
        '''Massage the interface output'''

        for entry in processed_data:
            if (entry['vlanName'].startswith('VLAN') or
                    entry['vlanName'] == "default"):
                entry['vlanName'] = f'vlan{entry["vlan"]}'

            if '_entryType' in entry:
                # This is a textfsm parsed entry, the interfaces list needs to
                # be massaged
                iflist = entry.get('interfaces', [])
                newlist = []
                for ele in iflist:
                    newlist.extend([expand_nxos_ifname(x)
                                   for x in ele.split(', ')])

                entry['interfaces'] = newlist
                continue

            if isinstance(entry['interfaces'], str):
                entry['interfaces'] = entry['interfaces'].split(',')
            else:
                entry['interfaces'] = entry['interfaces'][0].split(',')
        return processed_data

    def _clean_junos_data(self, processed_data, _):
        '''Massage the default name and interface list'''

        drop_indices = []

        for i, entry in enumerate(processed_data):
            if entry['vlan'] is None:
                drop_indices.append(i)
                continue

            if entry['vlanName'] == 'default':
                entry['vlanName'] = f'vlan{entry["vlan"]}'
            if entry['interfaces'] == [[None]]:
                entry['interfaces'] = []
            # We don't need the explicit .<vlan> tag for interfaces
            # to keep it consistent with the other devices, but we
            # cannot remove the VTEP info

            if entry['vlan'] != 'none':
                # MX has no VLAN, just BD, and so don't strip vlan
                # from interface name
                entry['interfaces'] = [x.split('.')[0].replace('*', '')
                                       if not x.startswith('vtep')
                                       else x.replace('*', '')
                                       for x in entry['interfaces']]
            entry['state'] = entry['state'].lower()
            name = entry.get('vlanName', '')
            if name.startswith('Vlan'):
                entry['vlanName'] = entry['vlanName'].lower()

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_ios_data(self, processed_data, _):
        '''Massage the interface list'''

        vlan_dict = {}
        drop_indices = []
        new_entries = []

        for i, entry in enumerate(processed_data):
            if entry.get('_entryType', '') == 'vlan':
                if entry['vlanName'] == 'default':
                    entry['vlanName'] = f'vlan{entry["vlan"]}'
                entry['vlanName'] = entry['vlanName'].strip()
                if entry['interfaces']:
                    newiflist = []
                    for ifname in entry['interfaces']:
                        newiflist.extend([expand_ios_ifname(x.strip())
                                          for x in ifname.split(',')])
                    if newiflist == ['']:
                        newiflist = []
                    entry['interfaces'] = newiflist
                else:
                    entry['interfaces'] = []
                entry['state'] = entry['state'].lower()
                if entry['state'] == 'act/unsup':
                    entry['state'] = 'unsupported'
                vlan_dict[entry['vlan']] = entry
            else:
                drop_indices.append(i)
                vlans = entry.get('_nativeVlan', '')
                if not vlans:
                    vlans = entry.get('_vlansStpFwd', '')
                if not vlans or vlans == 'none':
                    continue

                ifname = expand_ios_ifname(entry.get('ifname', ''))
                vlans = sum((
                    (list(range(*[int(j) + k
                                  for k, j in enumerate(i.split('-'))]))
                     if '-' in i else [i]) for i in vlans.split(',')), [])
                for vlan in vlans:
                    # IOS allows declaring a native VLAN without it being
                    # declared in show vlan. Handle that
                    if str(vlan) not in vlan_dict:
                        vlan_dict[str(vlan)] = {
                            'vlan': vlan,
                            'state': 'active',
                            'vlanName': f'vlan{vlan}',
                            'interfaces': []
                        }
                        new_entries.append(vlan_dict[str(vlan)])
                    vlan_dict[str(vlan)]['interfaces'].append(ifname)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        if new_entries:
            processed_data.extend(new_entries)
        return processed_data

    def _clean_iosxe_data(self, processed_data, raw_data):
        return self._clean_ios_data(processed_data, raw_data)
