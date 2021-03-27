import re
import numpy as np

from suzieq.poller.services.service import Service
from suzieq.utils import convert_rangestring_to_list


class EvpnVniService(Service):
    """evpnVni service. Different class because output needs to be munged"""

    def clean_json_input(self, data):
        """FRR JSON data needs some work"""

        devtype = data.get("devtype", None)
        if any(x == devtype for x in ["cumulus", "sonic", "linux"]):
            data['data'] = '[' + re.sub(r'}\n\n{\n', r'},\n\n{\n',
                                        data['data']) + ']'
            return data['data']

    def _clean_eos_data(self, processed_data, raw_data):
        new_entries = []

        if not processed_data:
            return processed_data

        for entry in processed_data:
            vni2vrfmap = {}
            for vrf in entry['_vrf2VniMap']:
                vni2vrfmap[entry['_vrf2VniMap'][vrf]] = vrf

            vtepMap = entry.get('_vlan2VtepMap', {})
            for vlan in entry['_vlan2VniMap']:
                new_entry = {}
                vni = entry['_vlan2VniMap'][vlan].get('vni', 0)
                new_entry['vni'] = vni
                new_entry['vrf'] = vni2vrfmap.get(vni, '')
                new_entry['state'] = entry['state']
                new_entry['ifname'] = entry['ifname']
                new_entry['vlan'] = vlan
                new_entry['priVtepIp'] = entry['priVtepIp']
                vteplist = vtepMap.get(vlan, {})
                vteplist = (vteplist.get('remoteVtepAddr', []) +
                            vteplist.get('remoteVtepAddr6', []))
                new_entry['remoteVtepList'] = vteplist
                new_entry['replicationType'] = entry['replicationType']
                new_entry['mcastGroup'] = entry['mcastGroup']
                if new_entry['vrf']:
                    new_entry['type'] = 'L3'
                else:
                    new_entry['type'] = 'L2'

                new_entries.append(new_entry)

        processed_data = new_entries
        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        """Clean out null entries among other cleanup"""

        del_indices = []
        for i, entry in enumerate(processed_data):
            if entry['vni'] is None:
                del_indices.append(i)
            if entry['mcastGroup'] and entry['mcastGroup'] != "0.0.0.0":
                entry['replicationType'] = 'multicast'
            elif entry['type'] != 'L3':
                entry['replicationType'] = 'ingressBGP'
                entry['mcastGroup'] = "0.0.0.0"
            else:
                entry['replicationType'] = ''
                entry['mcastGroup'] = "0.0.0.0"
                entry['remoteVtepList'] = None

        processed_data = np.delete(processed_data, del_indices).tolist()

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):
        """Merge peer records with VNI records to yield VNI-based records"""

        vni_dict = {}
        drop_indices = []

        for i, entry in enumerate(processed_data):
            if not entry['vni']:
                drop_indices.append(i)
                continue

            if entry['_entryType'] == 'VNI':
                type, vrf = entry['type'].split()
                if type == 'L3':
                    entry['vrf'] = vrf[1:-1]  # strip off '[' and ']'
                entry['type'] = type
                if 'sviState' in entry:
                    entry['state'] = entry['sviState'].split()[0].lower()
                if re.search(r'[0-9.]+', entry.get('replicationType', '')):
                    entry['mcastGroup'] = entry['replicationType']
                    entry['replicationType'] = 'multicast'
                elif entry['type'] != 'L3':
                    entry['replicationType'] = 'ingressBGP'
                    entry['mcastGroup'] = "0.0.0.0"
                else:
                    entry['replicationType'] = ''
                    entry['mcastGroup'] = "0.0.0.0"

                # we'll fill this with the peers entries
                entry['remoteVtepList'] = []
                entry['state'] = entry['state'].lower()
                entry['vlan'] = int(entry['vlan'])
                vni_dict[entry['vni']] = entry

            elif entry['_entryType'] == 'peers':
                vni_list = convert_rangestring_to_list(
                    entry.get('_vniList', ''))
                for vni in vni_list:
                    vni_entry = vni_dict.get(vni, None)
                    if vni_entry:
                        vni_entry['remoteVtepList'].append(entry['vni'])
                drop_indices.append(i)

            elif entry['_entryType'] == 'iface':
                if entry.get('encapType', '') != "VXLAN":
                    continue

                for vni in vni_dict:
                    if vni_dict[vni]['ifname'] != entry['ifname']:
                        continue
                    vni_dict[vni]['priVtepIp'] = entry.get('priVtepIp', '')
                    secIP = entry.get('secVtepIp', '')
                    if secIP == '0.0.0.0':
                        secIP = ''
                    vni_dict[vni]['secVtepIp'] = secIP
                    vni_dict[vni]['routerMac'] = entry.get('routerMac',
                                                           '00:00:00:00:00:00')
                drop_indices.append(i)

        processed_data = np.delete(processed_data, drop_indices).tolist()

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):

        newntries = {}

        for entry in processed_data:
            if entry['_entryType'] == 'instance':
                if entry['_vniList'] is None:
                    continue
                for i, vni in enumerate(entry['_vniList']):
                    irb_iflist = entry.get('_irbIfList', [])
                    vrflist = entry.get('_vrfList', [])
                    vlan = entry['_vlanList'][i]
                    irbif = f'irb.{vlan}'
                    try:
                        index = irb_iflist.index(irbif)
                        vrf = vrflist[index]
                    except ValueError:
                        vrf = ''
                    except IndexError:
                        vrf = ''

                    if vni not in newntries:
                        vni_entry = {
                            'vni': int(vni),
                            'remoteVtepList': [],
                            'type': 'L2',
                            'state': 'up',
                            'vlan': int(vlan),
                            'numRemoteVteps': 0,
                            'numMacs': 0,
                            'numArpNd': 0,
                            'vrf': vrf,
                            'os': 'junos'
                        }
                    newntries[vni] = vni_entry
                    continue
            elif entry['_entryType'] == 'l3':
                vni = int(entry.get('vni', '0'))
                priVtepIp = entry.get('priVtepIp', '')

                if not priVtepIp and not vni:
                    continue

                vni_entry = {
                    'vni': vni,
                    'remoteVtepList': [],
                    'priVtepIp': priVtepIp,
                    'type': 'L3',
                    'state': 'up',
                    'numRemoteVteps': 0,
                    'routerMac': entry['routerMac'],
                    'numMacs': 0,
                    'numArpNd': 0,
                    'mcastGroup': '0.0.0.0',
                    'vrf': entry['vrf'],
                    'os': 'junos'
                }
                newntries[vni] = vni_entry
                continue
            elif entry['_entryType'] == 'remote':
                priVtepIp = entry.get('priVtepIp', '[{"data": ""}]')[0]['data']
                for i, vni in enumerate(entry.get('_vniList', [])):
                    vni_entry = newntries.get(vni, {})
                    if not vni_entry:
                        vni_entry = {
                            'vni': int(vni),
                            'remoteVtepList': [],
                            'priVtepIp': priVtepIp,
                            'type': 'L2',
                            'state': 'up',
                            'numRemoteVteps': len(entry['_floodVtepList']),
                            'numMacs': 0,
                            'numArpNd': 0,
                            'os': 'junos'
                        }
                        newntries[vni] = vni_entry

                    vni_entry['priVtepIp'] = priVtepIp
                    if entry['replicationType'][i] == '0.0.0.0':
                        vni_entry['replicationType'] = 'ingressBGP'
                        vni_entry['mcastGroup'] = "0.0.0.0"
                    else:
                        vni_entry['replicationType'] = 'multicast'
                        vni_entry['mcastGroup'] = entry['replicationType'][i]

                    vni_entry['remoteVtepList'].append(
                        entry.get('_floodVtepList', ''))

        processed_data = list(newntries.values())
        return processed_data
