import re
from datetime import datetime

from dateparser import parse
import numpy as np

from suzieq.poller.worker.services.service import Service
from suzieq.shared.utils import (expand_nxos_ifname,
                                 get_timestamp_from_cisco_time,
                                 get_timestamp_from_junos_time)


class MroutesService(Service):
    """Mroutes servers."""

    def clean_json_input(self, data):
        """Junos JSON data for some older ver needs some work"""

        devtype = data.get("devtype", None)
        if devtype.startswith('junos'):
            data['data'] = data['data'].replace('}, \n    }\n', '} \n    }\n')
            return data['data']

        return data['data']

    def _fix_ipvers(self, entry):
        '''Fix IP version of entry'''
        if ':' in entry['prefix']:
            entry['ipvers'] = 6
        else:
            entry['ipvers'] = 4

    def _common_data_cleaner(self, processed_data, _):
        for entry in processed_data:
            self._fix_ipvers(entry)

        return processed_data

    def _clean_eos_data(self, processed_data, _):
        '''Massage EVPN routes'''
        for entry in processed_data:
            if entry['nexthopIps']:
                nexthop = entry['nexthopIps'][0]
                if 'vtepAddr' in nexthop:
                    nexthop = entry['nexthopIps'][0]
                    entry['nexthopIps'] = [nexthop['vtepAddr']]
                    entry['oifs'] = ['_nexthopVrf:default']
            elif entry.get('_vtepAddr', []):
                entry['nexthopIps'] = entry['_vtepAddr']
                entry['oifs'] = len(entry['nexthopIps']) * \
                    ['_nexthopVrf:default']
            entry['protocol'] = entry['protocol'].lower()
            entry['preference'] = int(entry.get('preference', 0))
            entry['metric'] = int(entry.get('metric', 0))
            self._fix_ipvers(entry)

        return processed_data