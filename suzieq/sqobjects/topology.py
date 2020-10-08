import typing
from collections import OrderedDict, defaultdict
from itertools import repeat
from dataclasses import dataclass

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from suzieq.sqobjects import interfaces, lldp, bgp, ospf, basicobj, address, evpnVni
from suzieq.sqobjects.basicobj import SqObject
from suzieq.exceptions import NoLLdpError, EmptyDataframeError, PathLoopError


class TopologyObj(basicobj.SqObject):
    def __init__(self, **kwargs):
        super().__init__(table='bgp', **kwargs)
        self._sort_fields = ["namespace", "hostname"]
        self._cat_fields = []
        self._valid_get_args = ['namespace', 'hostname', 'polled_neighbor',
                                'vrf']

    def get(self, **kwargs):
        try:
            self.validate_get_input(**kwargs)
        except Exception as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df
        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.get(**kwargs)


    # overriding parent because we want to take more arguments than the standard
    def summarize(self, namespace='', polled_neighbor=False) -> pd.DataFrame:
    
        return self.engine_obj.summarize(namespace=namespace, 
                                        polled_neighbor=polled_neighbor)