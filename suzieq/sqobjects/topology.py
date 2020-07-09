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
    def __init__(
        self,
        engine: str = "",
        hostname: typing.List[str] = [],
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        namespace: typing.List[str] = [],
        columns: typing.List[str] = ["default"],
        context=None,
    ) -> None:
        super().__init__(
            engine,
            hostname,
            start_time,
            end_time,
            view,
            namespace,
            columns,
            context=context,
            table='topology',
        )
        self._sort_fields = ["namespace", "hostname"]
        self._cat_fields = []

    def get(self, **kwargs):
    
        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.get(**kwargs)
    
    def summarize(self, **kwargs):
        """Summarize topology info for one or more namespaces"""

        return self.engine_obj.summarize(**kwargs)
