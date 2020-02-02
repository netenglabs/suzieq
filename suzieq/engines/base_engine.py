#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#


class SqEngine(object):
    def __init__(self):
        pass

    def get_table_df(self, cfg, schemas, **kwargs):
        raise NotImplementedError

    def get_object(self, objname: str):
        raise NotImplementedError


def get_sqengine(name: str = "modin"):
    if name == "spark":
        from .spark.engine import SqSparkEngine

        return SqSparkEngine()
    elif name == "modin":
        from .modin.engine import SqModinEngine

        return SqModinEngine()
    else:
        from .pandas.engine import SqPandasEngine

        return SqPandasEngine()

    return None
