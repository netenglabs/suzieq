#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import pandas as pd

from suzieq.engines.pandas.engineobj import SqEngineObject


class ospfObj(SqEngineObject):
    def get(self, **kwargs):

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        table = "ospfNbr"
        if "type" in kwargs:
            if kwargs.get("type", "interface") == "interface":
                table = "ospfIf"
            del kwargs["type"]

        df = self.get_valid_df(table, sort_fields, **kwargs)
        return df

    def summarize(self, **kwargs):
        """Describe the data"""
        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        table = "ospfNbr"
        if "type" in kwargs:
            if kwargs.get("type", "interface") == "interface":
                table = "ospfIf"
            del kwargs["type"]

        df = self.get_valid_df(table, sort_fields, **kwargs)

        if kwargs.get("groupby"):
            return df.groupby(kwargs["groupby"]).agg(lambda x: x.unique().tolist())
        else:
            return df.describe(include="all").fillna("-")

    def aver(self, **kwargs):
        """Assert that the OSPF state is OK"""
        raise NotImplementedError

    def top(self, what="transitions", n=5, **kwargs) -> pd.DataFrame:
        """Get the list of top stuff about OSPF"""
        raise NotImplementedError


if __name__ == "__main__":
    try:
        import fire

        fire.Fire(ospfObj)
    except ImportError:
        pass
