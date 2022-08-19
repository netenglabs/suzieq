import time

from nubia import command
import pandas as pd

from suzieq.cli.nubia_patch import argument
from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.ospf import OspfObj


@command("ospf", help="Act on OSPF data")
@argument(
    "ifname",
    description="Interface name(s), space separated"
)
@argument("vrf", description="VRF(s), space separated")
@argument("area", description="Area(s), space separated")
@argument("state", description="Select view based on OSPF state",
          choices=["full", "other", "passive", "!full", "!passive",
                   "!other"])
class OspfCmd(SqTableCommand):
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
            'ifname': ifname.split(),
            'vrf': vrf.split(),
            'area': area.split(),
            'state': state
        }

    @command("assert")
    @argument("result", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    def aver(self, result: str = 'all') -> pd.DataFrame:
        """
        Test OSPF runtime state is without errors
        """
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.aver,
                                namespace=self.namespace,
                                hostname=self.hostname,
                                columns=self._add_result_columns(self.columns),
                                result=result,
                                **self.lvars,
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)
