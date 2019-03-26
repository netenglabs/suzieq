#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import sys
import re
import json
from collections import OrderedDict

import pandas as pd
from termcolor import cprint
import typing
from nubia import command, argument, context

sys.path.append('/home/ddutt/work/')
import suzieq.livylib
from suzieq.utils import load_sq_config, get_schemas, get_query_df


@command("set")
@argument("datacenter", description="datacenter to qualify selection")
@argument("hostname", description="Name of host to qualify selection")
@argument("start_time",
          description="Start of time window in YYYY-MM-dd HH:mm:SS format")
@argument("end_time",
          description="End of time window in YYYY-MM-dd HH:mm:SS format")
def set_ctxt(hostname: typing.List[str] = [], start_time: str = '',
             end_time: str = '', datacenter: typing.List[str] = []):
    '''set certain contexts for subsequent commands. Cmd is additive'''
    plugin_ctx = context.get_context()

    if datacenter:
        plugin_ctx.datacenter = datacenter

    if hostname:
        plugin_ctx.hostname = hostname

    if start_time:
        plugin_ctx.start_time = start_time

    if end_time:
        plugin_ctx.end_time = end_time


@command("clear")
@argument("ctxt", description="Name of context you want to clear",
          choices=['all', 'datacenter', 'hostname', 'start-time', 'end_time'])
def clear_ctxt(ctxt: str):
    '''clear certain contexts for subsequent commands. Cmd is additive'''
    plugin_ctx = context.get_context()

    if ctxt == 'datacenter' or ctxt == 'all':
        plugin_ctx.datacenter = []

    if ctxt == 'hostname' or ctxt == 'all':
        plugin_ctx.hostname = []

    if ctxt == 'start-time' or ctxt == 'all':
        plugin_ctx.start_time = ''

    if ctxt == 'end-time' or ctxt == 'all':
        plugin_ctx.end_time = ''
