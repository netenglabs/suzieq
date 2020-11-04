from suzieq.poller.services.service import Service


class VlanService(Service):
    """Vlan service. Different class because Vlan is not right type for EOS"""

    def _clean_eos_data(self, processed_data, raw_data):
        '''Massage the interface output'''

        for entry in processed_data:
            entry['ifname'] = f'vlan{entry["vlan"]}'

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
                ifname = f'vlan{vlan}'

                if entry['ifname'] == 'bridge':
                    state = 'suspended'
                else:
                    state = 'active'
                if ifname not in entry_dict:
                    new_entry = {'ifname': ifname,
                                 'state': state,
                                 'vlan': vlan,
                                 'interfaces': set(),
                                 }
                    new_entries.append(new_entry)
                    entry_dict[ifname] = new_entry
                else:
                    new_entry = entry_dict[ifname]

                if entry['ifname'] != 'bridge':
                    new_entry['interfaces'].add(entry['ifname'])
                    new_entry['state'] = 'active'

        for entry in new_entries:
            entry['interfaces'] = list(entry['interfaces'])

        return new_entries

    def _clean_nxos_data(self, processed_data, raw_data):
        '''Massage the interface output'''

        for entry in processed_data:
            entry['ifname'] = f'vlan{entry["vlan"]}'
            entry['interfaces'] = entry['interfaces'][0].split()

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        '''Massage the default name and interface list'''

        for entry in processed_data:
            if entry['ifname'] == 'default':
                entry['ifname'] = f'vlan{entry["vlan"]}'
                if entry['interfaces'] == [[None]]:
                    entry['interfaces'] = []

        return processed_data
