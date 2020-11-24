from suzieq.poller.services.service import Service


class VlanService(Service):
    """Vlan service. Different class because Vlan is not right type for EOS"""

    def _clean_eos_data(self, processed_data, raw_data):
        '''Massage the interface output'''

        for entry in processed_data:
            if (entry['vlanName'].startswith('VLAN') or
                    entry['vlanName'] == "default"):
                entry['vlanName'] = f'vlan{entry["vlan"]}'

        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
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

    def _clean_nxos_data(self, processed_data, raw_data):
        '''Massage the interface output'''

        for entry in processed_data:
            if (entry['vlanName'].startswith('VLAN') or
                    entry['vlanName'] == "default"):
                entry['vlanName'] = f'vlan{entry["vlan"]}'
            if isinstance(entry['interfaces'], str):
                entry['interfaces'] = entry['interfaces'].split(',')
            else:
                entry['interfaces'] = entry['interfaces'][0].split(',')
        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        '''Massage the default name and interface list'''

        for entry in processed_data:
            if entry['vlanName'] == 'default':
                entry['vlanName'] = f'vlan{entry["vlan"]}'
            if entry['interfaces'] == [[None]]:
                entry['interfaces'] = []
            entry['state'] = entry['state'].lower()
            entry['vlanName'] = entry['vlanName'].lower()

        return processed_data
