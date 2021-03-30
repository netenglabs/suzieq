import time
from datetime import timedelta
from nubia import command, argument
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.ospf import OspfObj


@command("ospf", help="Act on OSPF data")
class OspfCmd(SqCommand):
    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        namespace: str = "",
        format: str = "",
        query_str: str = ' ',
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
            query_str=query_str,
            sqobj=OspfObj,
        )

    @command("show")
    @argument(
        "ifname", description="Space separated list of interface names to qualify"
    )
    @argument("state", description="Select view based on status",
              choices=["full", "other", "passive"])
    @argument("vrf", description="Space separated list of VRFs to qualify")
    def show(self, ifname: str = "", state: str = "", vrf: str = ""):
        """
        Show OSPF interface and neighbor info
        """
        if self.columns is None:
            return

        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname,
                                vrf=vrf.split(),
                                ifname=ifname.split(),
                                columns=self.columns,
                                state=state,
                                query_str=self.query_str,
                                namespace=self.namespace,
                                )

        df = self.sqobj.humanize_fields(df)

        # Transform the lastChangeTime into human terms
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("summarize")
    @argument(
        "ifname", description="Space separated list of interface names to qualify"
    )
    @argument("vrf", description="Space separated list of VRFs to qualify")
    @argument("state", description="BGP neighbor state to qualify", choices=["full"])
    @argument(
        "type",
        description="Type of OSPF information to show",
        choices=["neighbor", "interface"],
    )
    @argument("groupby", description="Space separated list of fields to summarize on")
    def summarize(
        self,
        ifname: str = "",
        vrf: str = "",
        state: str = "",
        type: str = "neighbor",
        groupby: str = "",
    ):
        """
        Summarize OSPF data
        """
        self._init_summarize()
        return self._post_summarize()

    @command("assert")
    @argument("vrf", description="VRF to assert OSPF state in")
    @argument("status", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    def aver(self, vrf: str = "", status: str = 'all') -> pd.DataFrame:
        """
        Test OSPF runtime state is good
        """
        if self.hostname:
            df = pd.DataFrame(
                {'error': ['ERROR: You cannot specify hostname with assert']})
            return self._gen_output(df)
        now = time.time()
        df = self.sqobj.aver(
            vrf=vrf.split(),
            namespace=self.namespace,
            status=status,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)

    @command("top")
    @argument("what", description="Field you want to see top for",
              choices=["flaps"])
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

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df, sort=False)
