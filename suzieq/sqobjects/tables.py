#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import sys
import os
from pathlib import Path
import pandas as pd

from suzieq.sqobjects import basicobj


class TablesObj(basicobj.SqObject):

    def get(self, **kwargs):
        '''Show the tables for which we have information'''
        dfolder = self.cfg['data-directory']
        df = None

        if dfolder:
            p = Path(dfolder)
            tables = [{'table': dir.parts[-1]} for dir in p.iterdir()
                      if dir.is_dir() and not dir.parts[-1].startswith('_')]
            datacenters = kwargs.get('datacenter', [])
            for dc in datacenters:
                tables = filter(
                    lambda x: os.path.exists('{}/{}/datacenter={}'.format(
                        dfolder, x['table'], dc)), tables)
            df = pd.DataFrame.from_dict(tables)

        return(df)

    def summarize(self, **kwargs):
        "Describes the fields for a given table"

        df = None
        table = kwargs.get('table', '')
        if table not in self.schemas:
            raise LookupError('ERROR: Unknown table {}'.format(table))
            return

        entries = [{'name': x['name'], 'type': x['type']}
                   for x in self.schemas[table]]
        df = pd.DataFrame.from_dict(entries)

        return(df)


if __name__ == '__main__':
    pass

