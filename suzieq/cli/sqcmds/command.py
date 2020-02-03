from pathlib import Path
import json
from collections import OrderedDict

import pandas as pd
from termcolor import cprint
from nubia import command, argument, context
import typing

from suzieq.engines import get_sqengine

@argument(
        "engine",
        description="which analytical engine to use",
        choices=["spark", "pandas"],
    )
@argument(
    "datacenter", description="Space separated list of datacenters to qualify"
)
@argument("hostname", description="Space separated list of hostnames to qualify")
@argument(
    "start_time", description="Start of time window in YYYY-MM-dd HH:mm:SS format"
)
@argument(
    "end_time", description="End of time window in YYYY-MM-dd HH:mm:SS format"
)
@argument(
    "view",
    description="view all records or just the latest",
    choices=["all", "latest"],
)
@argument("columns", description="Space separated list of columns, * for all")
class SqCommand:
    """Base Command Class for use with all verbs"""
    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        datacenter: str = "",
        columns: str = "default",
    ) -> None:
        self.ctxt = context.get_context()
        self._cfg = self.ctxt.cfg
        self._schemas = self.ctxt.schemas

        if not datacenter and self.ctxt.datacenter:
            self.datacenter = self.ctxt.datacenter
        else:
            self.datacenter = datacenter.split()
        if not hostname and self.ctxt.hostname:
            self.hostname = self.ctxt.hostname
        else:
            self.hostname = hostname.split()

        if not start_time and self.ctxt.start_time:
            self.start_time = self.ctxt.start_time
        else:
            self.start_time = start_time

        if not end_time and self.ctxt.end_time:
            self.end_time = self.ctxt.end_time
        else:
            self.end_time = end_time

        self.view = view
        self.columns = columns.split()
        if engine:
            self.engine = get_sqengine(engine)
        else:
            self.engine = self.ctxt.engine

    @property
    def cfg(self):
        return self._cfg

    @property
    def schemas(self):
        return self._schemas

    def show(self, **kwargs):
        raise NotImplementedError

    def analyze(self, **kwargs):
        raise NotImplementedError

    def aver(self, **kwargs):
        raise NotImplementedError

    def summarize(self, **kwargs):
        raise NotImplementedError

    def top(self, **kwargs):
        raise NotImplementedError
