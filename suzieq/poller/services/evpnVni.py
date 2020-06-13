from suzieq.poller.services.service import Service
import re
import numpy as np


class EvpnVniService(Service):
    """evpnVni service. Different class because output needs to be munged"""

    def clean_json_input(self, data):
        """FRR JSON data needs some work"""

        if data.get("devtype", None) == "cumulus":
            data['data'] = '[' + re.sub(r'}\n\n{\n', r'},\n\n{\n',
                                        data['data']) + ']'
            return data['data']

    def clean_data(self, processed_data, raw_data):

        devtype = self._get_devtype_from_input(raw_data)
        if devtype == 'cumulus':
            processed_data = self._clean_cumulus_data(processed_data, raw_data)
        elif devtype == 'nxos':
            processed_data = self._clean_nxos_data(processed_data, raw_data)
        elif devtype == "junos":
            processed_data = self._clean_junos_data(processed_data, raw_data)

        return super().clean_data(processed_data, raw_data)

    def _clean_cumulus_data(self, processed_data, raw_data):
        """Clean out null entries among other cleanup"""

        del_indices = []
        for i, entry in enumerate(processed_data):
            if entry['vni'] is None:
                del_indices.append(i)
            if entry['mcastGroup']:
                entry['replicationType'] = 'multicast'
            else:
                entry['replicationType'] = 'ingressBGP'
                entry['mcastGroup'] = "00:00:00:00:00:00"

        for idx in del_indices:
            del processed_data[idx]

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):
        """Merge peer records with VNI records to yield VNI-based records"""

        vni_dict = {}
        drop_indices = []

        for i, entry in enumerate(processed_data):
            if entry['_rectype'] == 'VNI':
                type, vrf = entry['type'].split()
                if type == 'L3':
                    entry['vrf'] = vrf[1:-1]  # strip off '[' and ']'
                entry['type'] = type
                if 'sviState' in entry:
                    entry['state'] = entry['sviState'].split()[0].lower()
                if re.search(r'[0-9.]+', entry.get('replicationType', '')):
                    entry['mcastGroup'] = entry['replicationType']
                    entry['replicationType'] = 'multicast'
                else:
                    entry['replicationType'] = 'ingressBGP'
                    entry['mcastGroup'] = "00:00:00:00:00:00"

                # we'll fill this with the peers entries
                entry['remoteVtepList'] = []
                entry['state'] = entry['state'].lower()
                entry['vlan'] = int(entry['vlan'])
                vni_dict[entry['vni']] = entry

            elif entry['_rectype'] == 'peers':
                vni_list = entry['vni'].split(',')
                for vni in vni_list:
                    vni_entry = vni_dict.get(vni, None)
                    if vni_entry:
                        vni_entry['remoteVtepList'].append(entry['_peerIp'])
                        vni_entry['routerMac'] = entry['routerMac']
                drop_indices.append(i)

            elif entry['_rectype'] == 'iface':
                if entry['encapType'] != "VXLAN":
                    continue
                for vni in vni_dict:
                    if vni_dict[vni]['ifname'] != entry['ifname']:
                        continue
                    vni_dict[vni]['srcVtepIp'] = entry['srcVtepIp']
                drop_indices.append(i)

        processed_data = np.delete(processed_data, drop_indices).tolist()

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):

        newntries = {}

        for entry in processed_data:
            srcVtepIp = entry['srcVtepIp'][0]['data']
            for i, vni in enumerate(entry['_vniList']):
                if vni not in newntries:
                    vni_entry = {'vni': int(vni),
                                 'remoteVtepList': [],
                                 'srcVtepIp': srcVtepIp,
                                 'type': 'L2',
                                 'state': 'up',
                                 'os': 'junos'
                                 }

                    if entry['replicationType'][i] == '0.0.0.0':
                        vni_entry['replicationType'] = 'ingressBGP'
                        vni_entry['mcastGroup'] = "00:00:00:99:00:00"
                    else:
                        vni_entry['replicationType'] = 'multicast'
                        vni_entry['mcastGroup'] = entry['replicationType'][i]

                    newntries[vni] = vni_entry

                vni_entry = newntries[vni]
                vni_entry['remoteVtepList'].append(entry['remoteVtepList'])

        processed_data = list(newntries.values())
        return processed_data
