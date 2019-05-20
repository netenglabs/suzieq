#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import os
from concurrent.futures import ProcessPoolExecutor as Executor

from suzieq.utils import load_sq_config, get_schemas


class SQEngine(object):

    def __init__(self):
        pass

    def get_table_df(self, cfg, schemas, **kwargs):
        raise NotImplementedError

    def get_display_fields(self, table: str, columns: list,
                           schema: dict) -> list:
        '''Return the list of display fields for the given table'''

        if columns == ['default']:
            fields = [f['name']
                      for f in sorted(schema, key=lambda x: x.get('display',
                                                                  1000))
                      if f.get('display', None)]

            if 'datacenter' not in fields:
                fields.insert(0, 'datacenter')

        elif columns == ['*']:
            fields = [f['name'] for f in schema]
        else:
            sch_flds = [f['name'] for f in schema]

            fields = [f for f in columns if f in sch_flds]

        return fields

    def get_latest_files(self, folder, start='', end='') -> list:
        lsd = []

        if start:
            ssecs = pd.to_datetime(
                start, infer_datetime_format=True).timestamp()*1000
        else:
            ssecs = 0

        if end:
            esecs = pd.to_datetime(
                end, infer_datetime_format=True).timestamp()*1000
        else:
            esecs = 0

        ts_dirs = False
        pq_files = False

        for root, dirs, files in os.walk(folder):
            flst = None
            if dirs and dirs[0].startswith('timestamp') and not pq_files:
                flst = self.get_latest_ts_dirs(dirs, ssecs, esecs)
                ts_dirs = True
            elif files and not ts_dirs:
                flst = self.get_latest_pq_files(files, root, ssecs, esecs)
                pq_files = True

            if flst:
                lsd.append(os.path.join(root, flst[-1]))

        return lsd

    def get_latest_ts_dirs(self, dirs, ssecs, esecs):
            newdirs = None

            if not ssecs and not esecs:
                dirs.sort(key=lambda x: int(x.split('=')[1]))
                newdirs = dirs
            elif ssecs and not esecs:
                newdirs = list(filter(lambda x: int(x.split('=')[1]) > ssecs,
                                      dirs))
                if not newdirs:
                    # FInd the entry most adjacent to this one
                    newdirs = list(
                        filter(lambda x: int(x.split('=')[1]) < ssecs,
                               dirs))
            elif esecs and not ssecs:
                newdirs = list(filter(lambda x: int(x.split('=')[1]) < esecs,
                                      dirs))
            else:
                newdirs = list(filter(lambda x: int(x.split('=')[1]) < esecs
                                      and int(x.split('=')[1]) > ssecs, dirs))
                if not newdirs:
                    # FInd the entry most adjacent to this one
                    newdirs = list(
                        filter(lambda x: int(x.split('=')[1]) < ssecs,
                               dirs))

            return newdirs

    def get_latest_pq_files(self, files, root, ssecs, esecs):

            newfiles = None

            if not ssecs and not esecs:
                files.sort(key=lambda x: os.path.getctime(
                    '%s/%s' % (root, x)))
                newfiles = files
            elif ssecs and not esecs:
                newfiles = list(filter(
                    lambda x: os.path.getctime('%s/%s' % (root, x)) > ssecs,
                    files))
                if not newfiles:
                    # FInd the entry most adjacent to this one
                    newfiles = list(filter(
                        lambda x: os.path.getctime('{}/{}'.format(
                            root, x)) < ssecs, files))
            elif esecs and not ssecs:
                newfiles = list(filter(
                    lambda x: os.path.getctime('%s/%s' % (root, x)) < esecs,
                    files))
            else:
                newfiles = list(filter(
                    lambda x: os.path.getctime('%s/%s' % (root, x)) < esecs
                    and os.path.getctime('%s/%s' % (root, x)) > ssecs, files))
                if not newfiles:
                    # Find the entry most adjacent to this one
                    newfiles = list(filter(
                        lambda x: os.path.getctime('%s/%s'
                                                   % (root, x)) < ssecs,
                        files))
            return newfiles


def get_sqengine(name: str = 'pandas'):
    if name == 'pandas':
        try:
            from .pandas_engine import SQPandasEngine

            return(SQPandasEngine())
        except ImportError:
            return None

    return None

