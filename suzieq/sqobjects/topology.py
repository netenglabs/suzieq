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

# TODO:
#  topology for different VRFs?
#  iBGP vs eBGP?
#  color by device type?
#  physical topology without LLDP -- is this possible?
#  how to draw multiple topologies
#  be able to ask if a node has neighbors by type (physical, overlay, protocol, etc)
#  questions
#    * without knowing hierarchy, labels or tags it's unclear how to group things for good picture
# how could we add state of connection (like Established) per protocol



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
