#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import sys

from nubia import context
from nubia import exceptions
from nubia import eventbus

sys.path.append('/home/ddutt/work/')
from suzieq.utils import load_sq_config, get_schemas


class NubiaSuzieqContext(context.Context):

    def __init__(self):
        self.cfg = load_sq_config(validate=False)

        self.schemas = get_schemas(self.cfg['schema-directory'])

        self.datacenter = ''
        self.hostname = ''
        self.start_time = ''
        self.end_time = ''
        self.exec_time = ''
        self.engine = 'pandas'
        self.system_df = {}
        self.sort_fields = []
        super().__init__()

    def on_connected(self, *args, **kwargs):
        pass

    def on_cli(self, cmd, args):
        # dispatch the on connected message
        self.verbose = args.verbose
        self.registry.dispatch_message(eventbus.Message.CONNECTED)

    def on_interactive(self, args):
        self.verbose = args.verbose
        ret = self._registry.find_command("connect").run_cli(args)
        if ret:
            raise exceptions.CommandError("Failed starting interactive mode")
        # dispatch the on connected message
        self.registry.dispatch_message(eventbus.Message.CONNECTED)

