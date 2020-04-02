import time
from datetime import timedelta
from nubia import command
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.bgp import BgpObj


@command("bgp", help="Act on BGP data")
class BgpCmd(SqCommand):
    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        namespace: str = "",
        format: str = "",
        columns: str = "default",
    ) -> None:
        super().__init__(
            engine=engine,
            hostname=hostname,
            start_time=start_time,
            end_time=end_time,
            view=view,
            namespace=namespace,
            columns=columns,
            format=format,
            sqobj=BgpObj,
        )

    @command("show")
    def show(self):
        """
        Show bgp info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.sqobj.get(
            hostname=self.hostname, columns=self.columns,
            namespace=self.namespace
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("summarize", help="Provide summary info about BGP per namespace")
    def summarize(self):
        """
        Summarize bgp info
        """
        self._init_summarize()

        # Convert columns into human friendly format
        if (not self.summarize_df.empty) and ('upTimes' in self.summarize_df.T.columns):
            self.summarize_df.loc['upTimes'] = self.summarize_df.loc['upTimes'] \
                .map(lambda x: [str(timedelta(seconds=int(i))) for i in x])

        return self._post_summarize()
