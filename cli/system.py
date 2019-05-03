#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import basicobj


class systemObj(basicobj.SQObject):

    sort_fields = ['datacenter', 'hostname']

    def get(self, **kwargs):
        '''Retrieve the selected data'''
        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        df = self.get_valid_df('system', sort_fields, **kwargs)
        return(df)

    def describe(self, **kwargs):
        '''Describe the data'''

        if self.ctxt.sort_fields is None:
            sort_fields = None
        else:
            sort_fields = self.sort_fields

        df = self.get_valid_df('system', sort_fields, **kwargs)

        if not df.empty:
            if kwargs.get('groupby'):
                return(df
                       .groupby(kwargs['groupby'])
                       .agg(lambda x: x.unique().tolist()))
            else:
                return(df
                       .describe(include='all')
                       .fillna('-'))


if __name__ == '__main__':
    try:
        import fire
        fire.Fire(systemObj)
    except ImportError:
        pass



