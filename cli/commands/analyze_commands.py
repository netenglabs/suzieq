#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#


import re
import sys
from pathlib import Path
import json
from collections import OrderedDict


import pandas as pd
from termcolor import cprint
from nubia import command, argument
import typing

sys.path.append('/home/ddutt/work/')
from suzieq.livylib import get_livysession, exec_livycode
from suzieq.utils import load_sq_config, get_schemas
from suzieq.utils import get_table_df


@command('analyze', help="Analyze this")
class AnalyzeCommand:

    @argument("hostname", description="Name of host to qualify selection")
    @argument("start_time",
              description="Start of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("end_time",
              description="End of time window in YYYY-MM-dd HH:mm:SS format")
    @argument("view", description="view all records or just the latest",
              choices=["all", "latest"])
    def __init__(self, hostname: typing.List[str] = [], start_time: str = '',
                 end_time: str = '', view: str = 'latest') -> None:
        self._cfg = load_sq_config(validate=False)
        self._schemas = get_schemas(self._cfg['schema-directory'])
        self.hostname = hostname
        self.start_time = start_time
        self.end_time = end_time
        self.view = view

    @property
    def cfg(self):
        return self._cfg

    @property
    def schemas(self):
        return self._schemas
    """show various pieces of information"""

    @command('bgp')
    @argument("peer", description="Name of peer to qualify show")
    @argument("vrf", description="VRF to qualify show")
    @argument("state", description="BGP neighbor state to qualify",
              choices=["Established", "NotEstd"])
    def analyze_bgp(self, peer: typing.List[str] = None,
                    vrf: typing.List[str] = None, state: str = ''):
        """
        Show BGP
        """
        order_by = 'order by hostname, vrf, peer'
        df = get_table_df('bgp', self.start_time, self.end_time,
                          self.view, order_by, self.cfg, self.schemas,
                          hostname=self.hostname, vrf=vrf, peer=peer,
                          state=state)
        print(df)

    @command('interface')
    @argument("peer", description="Name of peer to qualify show")
    @argument("vrf", description="VRF to qualify show")
    @argument("state", description="BGP neighbor state to qualify",
              choices=["Established", "NotEstd"])
    def analyze_interface(self, peer: typing.List[str] = None,
                          vrf: typing.List[str] = None, state: str = ''):
        """
        Show BGP
        """
        order_by = 'order by hostname, vrf, peer'
        df = get_table_df('bgp', self.start_time, self.end_time,
                          self.view, order_by, self.cfg, self.schemas,
                          hostname=self.hostname, vrf=vrf, peer=peer,
                          state=state)
        print(df)


