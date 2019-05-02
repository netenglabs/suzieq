#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import sys

import basicobj
try:
    import fire
except ImportError:
    pass


class OspfObj(basicobj.SQObject):

    sort_fields = ['datacenter', 'hostname', 'vrf', 'ifname']

    def get(self, **kwargs):

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        table = 'ospfNbr'
        if 'type' in kwargs:
            if kwargs.get('type', 'interface') == 'interface':
                table = 'ospfIf'
            del kwargs['type']

        df = self.get_valid_df(table, sort_fields, **kwargs)
        return(df)

    def describe(self, **kwargs):

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        table = 'ospfNbr'
        if 'type' in kwargs:
            if kwargs.get('type', 'interface') == 'interface':
                table = 'ospfIf'
            del kwargs['type']

        df = self.get_valid_df(table, sort_fields, **kwargs)

        if not df.empty:
            return(df
                   .describe(include='all')
                   .fillna('-'))


if __name__ == '__main__':
    fire.Fire(OspfObj)


