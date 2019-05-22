#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

import pandas as pd

from .engineobj import SQEngineObject


class interfacesObj(SQEngineObject):

    def aver(self, what='mtu-match', **kwargs) -> pd.DataFrame:
        raise NotImplementedError

    def top(self, what='transitions', n=5, **kwargs) -> pd.DataFrame:
        '''Get the list of top link changes'''
        raise NotImplementedError
