import re
from datetime import datetime

from dateparser import parse
import numpy as np

from suzieq.poller.worker.services.service import Service
from suzieq.shared.utils import (expand_nxos_ifname,
                                 get_timestamp_from_cisco_time,
                                 get_timestamp_from_junos_time)


class MroutesService(Service):
    """Mroutes service."""

    def clean_json_input(self, data):
        """Junos JSON data for some older ver needs some work"""

        devtype = data.get("devtype", None)
        if devtype.startswith('junos'):
            data['data'] = data['data'].replace('}, \n    }\n', '} \n    }\n')
            return data['data']

        return data['data']

    def _fix_ipvers(self, entry):
        '''Fix IP version of entry'''
        if ':' in entry['group']:
            entry['ipvers'] = 6
        else:
            entry['ipvers'] = 4

    def _fix_star_source(self, entry):
        '''Make 0.0.0.0 source a * as convention.'''
        if entry['source'] and '0.0.0.0' in entry['source']:
            entry['source'] = '*'

    def _common_data_cleaner(self, processed_data, _):

        for entry in processed_data:
            self._fix_ipvers(entry)
            self._fix_star_source(entry)

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):
        reprocessed_data = {}
        for entry in processed_data:
            unique = '-'.join([entry['vrf'],entry['group']])
            if unique in reprocessed_data.keys():
                reprocessed_data[unique]['oifList'].append(entry['oifList'])
                
            else:
                if not isinstance(entry['oifList'], list):
                    entry['oifList'] = [entry['oifList']]
                reprocessed_data.update({
                    unique: {
                        'oifList': entry['oifList'],
                        'group': entry['group'],
                        'source': entry['source'],
                        'vrf': entry['vrf'],
                        'incomingIf': entry['incomingIf'],
                        'rpfNeighbor': entry['rpfNeighbor']
                    }
                })

                processed_data = list(reprocessed_data.values())

                return processed_data
