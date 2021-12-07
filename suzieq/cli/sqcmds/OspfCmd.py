import time
from nubia import command, argument
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.ospf import OspfObj


@command("ospf", help="Act on OSPF data")
class OspfCmd(SqCommand):
    """OSPFv2 protocol information"""

    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "",
        namespace: str = "",
        format: str = "",  # pylint: disable=redefined-builtin
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
        "ifname",
        description="Space separated list of interface names to qualify"
    )
    @argument("state", description="Select view based on status",
              choices=["full", "other", "passive"])
    @argument("vrf", description="Space separated list of VRFs to qualify")
    def show(self, ifname: str = "", state: str = "", vrf: str = ""):
        """Show OSPF interface and neighbor info
        """
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

        # Transform the lastChangeTime into human terms
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("assert")
    @argument("vrf", description="VRF to assert OSPF state in")
    @argument("status", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    def aver(self, vrf: str = "", status: str = 'all') -> pd.DataFrame:
        """
        Test OSPF runtime state is without errors
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
