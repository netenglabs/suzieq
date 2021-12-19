import time
from nubia import command
from suzieq.cli.nubia_patch import argument
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.ospf import OspfObj


@command("ospf", help="Act on OSPF data")
@argument(
    "ifname",
    description="Space separated list of interface names to qualify"
)
@argument("vrf", description="Space separated list of VRFs to qualify")
@argument("area", description="OSPF area to filter by")
@argument("state", description="Select view based on OSPF state",
          choices=["full", "other", "passive", "!full", "!passive",
                   "!other"])
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
            ifname: str = '',
            vrf: str = '',
            area: str = '',
            state: str = ''
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
        self.lvars = {
            'ifname': ifname,
            'vrf': vrf,
            'area': area,
            'state': state
        }

    @command("assert")
    @argument("status", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    def aver(self, status: str = 'all') -> pd.DataFrame:
        """
        Test OSPF runtime state is without errors
        """
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.aver,
                                namespace=self.namespace,
                                hostname=self.hostname,
                                status=status,
                                **self.lvars,
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)
