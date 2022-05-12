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

        devtype = data.get("devtype", None)
        if devtype.startswith('junos'):
            data['data'] = data['data'].replace('}, \n    }\n', '} \n    }\n')
            return data['data']
        return data['data']

    def _clean_eos_data(self, processed_data, raw_data):

        pre_processed_data = {}
        # This handles the static group command output only
        # will update once some dynamic group output is available
        for data in raw_data:
            json_data = json.loads(data['data'])
            for interface in json_data['intfAddrs']:
                for s_g in interface['groupAddrsList']:
                    sg = '-'.join(s_g['sourceAddr'],s_g['groupAddr'])
                    if pre_processed_data.get(sg):
                        pre_processed_data.get(sg).append(interface)
                    else:
                        pre_processed_data[sg] = [interface]

        processed_data = []
        for k, v in pre_processed_data.items():
            s_g = k.split('-')
            processed_data.append(
                'source': s_g[0],
                'group': s_g[1],
                'interfaceList': v,
                'flag': 'Static',
            )

        breakpoint()

        return processed_data
