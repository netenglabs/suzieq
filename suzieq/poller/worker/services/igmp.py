import re
from datetime import datetime

from dateparser import parse
import numpy as np

import json

from suzieq.poller.worker.services.service import Service



class IgmpService(Service):
    """Igmp Service."""

    def clean_json_input(self, data):
        """Junos JSON data for some older ver needs some work"""
        pass

    def _clean_eos_data(self, _, raw_data):
        processed_data = []
        pre_processed_data = {}
        # This handles the static group command output only
        # will update once some dynamic group output is available
        for data in raw_data:
            if 'vrf' in data.get('cmd'):
                cmd = data['cmd'].split()
                vrf = cmd[cmd.index('vrf')+1]
            else:
                vrf = 'n/a'
            if vrf not in pre_processed_data.keys():
                pre_processed_data.update({vrf: {}})
            if isinstance(data['data'], str):
                json_data = json.loads(data.get('data'))
            else:
                json_data = None
            if json_data:
                if json_data.get('intfAddrs'):
                    for interface in json_data['intfAddrs']:
                        if json_data['intfAddrs'][interface]['groupAddrsList']:
                            for s_g in json_data['intfAddrs'][interface]['groupAddrsList']:
                                group = s_g['groupAddr']
                                if pre_processed_data[vrf].get(group):
                                    pre_processed_data[vrf].get(group).append(interface)
                                else:
                                    pre_processed_data[vrf][group] = [interface]
                if json_data.get('groupList'):
                    for group in json_data['groupList']:
                        
                        group_address = group['groupAddress']
                        interface = group['interfaceName']
                        if pre_processed_data[vrf].get(group_address):
                            pre_processed_data[vrf].append(interface)
                        else:
                            pre_processed_data[vrf][group_address] = [interface]
                        processed_data.append({
                            'group': group['groupAddress'],
                            'interfaceList': [],
                            'flag': 'Dynamic'
                        })

        for vrf, groups in pre_processed_data.items():
            for group in groups.keys():
                processed_data.append({
                    'vrf': vrf,
                    'group': group,
                    'interfaceList': groups[group],
                    'flag': '',
                })
        return processed_data

    def _clean_nxos_data(self, processed_data, _):
        """NXOS data returned from the textfsm template must be munged to a different format"""
        pre_processed_data = {}
        
        for item in processed_data:
            if item['vrf'] in pre_processed_data:
                if item['group'] in pre_processed_data[item['vrf']]:
                    pre_processed_data[item['vrf']][item['group']].append(item['interface'])
                else:
                    pre_processed_data[item['vrf']].update({
                        item['group']: [item['interface']]
                    })
            else:
                pre_processed_data.update({
                    item['vrf']: {item['group']: [item['interface']]}
                })

        processed_data = []

        for vrf, groups in pre_processed_data.items():
            for group in pre_processed_data[vrf]:
                processed_data.append({
                    'vrf': vrf,
                    'group': group,
                    'interfaceList': pre_processed_data[vrf][group],
                })

        return processed_data
