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
            sqobj=OspfObj,
        )

    @command("show")
    @argument(
        "ifname", description="Space separated list of interface names to qualify"
    )
    @argument("vrf", description="Space separated list of VRFs to qualify")
    @argument("state", description="BGP neighbor state to qualify", choices=["full"])
    def show(self, ifname: str = "", vrf: str = "", state: str = ""):
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

        df = self.sqobj.get(
            hostname=self.hostname,
            vrf=vrf.split(),
            ifname=ifname.split(),
            state=state,
            columns=self.columns,
            namespace=self.namespace,
        )

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
        # TODO: time in this field looks ugly
        #  it shows too many fields, we want it to look like BGP estdTime does in bgp summarize
        if not self.summarize_df.empty and 'lastChangeTime' in self.summarize_df.index:
            self.summarize_df.loc['lastChangeTime'] = self.summarize_df.loc['lastChangeTime'] \
                .map(lambda x: [str(pd.to_timedelta(i)) for i in x])

        return self._post_summarize()

    @command("assert")
    @argument("ifname", description="interface name to check OSPF on")
    @argument("vrf", description="VRF to assert OSPF state in")
    def aver(self, ifname: str = "", vrf: str = "") -> pd.DataFrame:
        """
        Test OSPF runtime state is good
        """
        now = time.time()
        df = self.sqobj.aver(
            hostname=self.hostname,
            vrf=vrf.split(),
            ifname=ifname.split(),
            namespace=self.namespace,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)

    @command("top")
    @argument(
        "what", description="Field you want to see top for", choices=["transitions"]
    )
    @argument("count", description="How many top entries")
    def top(self, what: str = "transitions", count: int = 5):
        """
        Show top n entries based on specific field
        """
        if self.columns is None:
            return

        now = time.time()

        df = self.sqobj.top(
            hostname=self.hostname,
            what=what,
            n=count,
            columns=self.columns,
            namespace=self.namespace,
        )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
