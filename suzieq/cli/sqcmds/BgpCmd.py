import time
from datetime import timedelta
from nubia import command

import pandas as pd

from suzieq.cli.nubia_patch import argument
from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.bgp import BgpObj


@command("bgp", help="Act on BGP data")
@argument("vrf", description="vrf name to qualify")
@argument("state", description="status of the session to match",
          choices=["Established", "NotEstd", "dynamic"])
@argument("peer",
          description=("IP address, in quotes, or the interface name, "
                       "of peer to qualify output"))
class BgpCmd(SqCommand):
    """BGP protocol information"""

    def __init__(
            self,
            engine: str = "",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "",
            namespace: str = "",
            format: str = "",  # pylint: disable=redefined-builtin
            columns: str = "default",
            query_str: str = ' ',
            vrf: str = '',
            state: str = '',
            peer: str = ''
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
            query_str=query_str,
            sqobj=BgpObj,
        )
        self.lvars = {
            'vrf': vrf.split(),
            'state': state,
            'peer': peer.split(),
        }

    def _clean_output(self, df) -> pd.DataFrame:
        """Make upTime look good"""
        if df.empty:
            return df

        if "estdTime" in df.columns:
            df['estdTime'] = df.estdTime.apply(
                lambda x: str(timedelta(milliseconds=int(x))))
        elif 'upTimeStat' in df.columns:
            df.loc['upTimeStat'] = df \
              .loc['upTimeStat'] \
              .map(lambda x: [str(timedelta(milliseconds=int(i))) for i in x])

        return df.dropna(how='any')

    @command("show")
    def show(self):
        """Show BGP info
        """

        if (self.columns != ['default'] and self.columns != ['*'] and
                'state' not in self.columns):
            self.lvars['addnl_fields'] = ['state']

        return super().show()

    @command("assert")
    @argument("status", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    def aver(self, status: str = "all") -> pd.DataFrame:
        """Assert BGP is functioning properly"""

        now = time.time()

        df = self._invoke_sqobj(self.sqobj.aver,
                                namespace=self.namespace,
                                hostname=self.hostname,
                                status=status,
                                **self.lvars,
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)
