import time
from datetime import timedelta
from nubia import command, argument
import pandas as pd

from suzieq.utils import humanize_timestamp
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
        query_str: str = ' ',
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
    @argument("vrf", description="vrf name to qualify")
    @argument("peer", description="IP address, in quotes, or the interface name, of peer to qualify output")
    @argument("state", description="status of the session to match",
              choices=["Established", "NotEstd"])
    def show(self, state: str = "", vrf: str = '', peer: str = ''):
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

        if (self.columns != ['default'] and self.columns != ['*'] and
                'state' not in self.columns):
            addnl_fields = ['state']
        else:
            addnl_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname, columns=self.columns,
                                namespace=self.namespace, state=state,
                                addnl_fields=addnl_fields,
                                query_str=self.query_str,
                                vrf=vrf.split(), peer=peer.split()
                                )

        if 'estdTime' in df.columns and not df.empty:
            df['estdTime'] = humanize_timestamp(df.estdTime,
                                                self.cfg.get('analyzer', {})
                                                .get('timezone', None))

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("summarize", help="Provide summary info about BGP per namespace")
    def summarize(self):
        """
        Summarize bgp info
        """
        self._init_summarize()
        return self._post_summarize()

    @command("assert")
    @argument("vrf", description="Only assert BGP state in this VRF")
    @argument("status", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    def aver(self, vrf: str = "", status: str = "all") -> pd.DataFrame:
        """Assert BGP is functioning properly"""

        now = time.time()
        df = self._invoke_sqobj(self.sqobj.aver,
                                vrf=vrf.split(),
                                namespace=self.namespace,
                                status=status,
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)

    @command("top")
    @argument(
        "what", description="Field you want to see top for",
        choices=["flaps", "updatesRx", "updatesTx", "uptime"]
    )
    @argument("count", description="How many top entries")
    @argument("reverse", description="True see Bottom n",
              choices=["True", "False"])
    def top(self, what: str = "flaps", count: int = 5, reverse: str = "False"):
        """
        Show top n entries based on specific field
        """
        if self.columns is None:
            return

        now = time.time()

        what_map = {
            "flaps": "numChanges",
            "updatesTx": "updatesTx",
            "updatesRx": "updatesRx",
            "uptime": "estdTime",
        }

        df = self._invoke_sqobj(self.sqobj.top,
                                hostname=self.hostname,
                                what=what_map[what],
                                n=count,
                                reverse=reverse == "True" or False,
                                columns=self.columns,
                                query_str=self.query_str,
                                namespace=self.namespace,
                                )
        if not df.empty and ('estdTime' in df.columns):
            df['estdTime'] = humanize_timestamp(df.estdTime,
                                                self.cfg.get('analyzer', {})
                                                .get('timezone', None))

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df, sort=False)
