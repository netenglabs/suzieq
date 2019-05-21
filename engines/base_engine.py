#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import os
import pandas as pd


class SQEngine(object):

    def __init__(self):
        pass

    def get_table_df(self, cfg, schemas, **kwargs):
        raise NotImplementedError

    def get_object(self, objname: str):
        raise NotImplementedError


def get_sqengine(name: str = 'pandas'):
    if name == 'pandas':
        try:
            from .pandas.engine import SQPandasEngine

            return(SQPandasEngine())
        except ImportError:
            return None

    return None

