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
        if '0.0.0.0' in entry['source']:
            entry['source'] = '*'

    # def _clean_nxos_data(self, processed_data, _):
    #     print(processed_data)

    #     return processed_data

    def _common_data_cleaner(self, processed_data, _):

        print(processed_data)
        for entry in processed_data:
            self._fix_ipvers(entry)
            self._fix_star_source(entry)

        return processed_data
