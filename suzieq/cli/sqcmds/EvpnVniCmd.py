import time
from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.evpnVni import EvpnvniObj


@command("evpnVni", help="Act on EVPN VNI data")
@argument("vni", description="VNI ID(s), space separated")
@argument("priVtepIp", description="Primary VTEP IP(s), space separated")
class EvpnVniCmd(SqTableCommand):
    """EVPN information such as VNI/VLAN mapping, VTEP IPs etc."""

    def __init__(
            self,
            engine: str = "",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "",
            namespace: str = "",
            format: str = "",  # pylint: disable=redefined-builtin
            query_str: str = " ",
            columns: str = "default",
            vni: str = '',
            priVtepIp: str = '',
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
            sqobj=EvpnvniObj,
        )
        self.lvars = {
            'vni': vni,
            'priVtepIp': priVtepIp.split()
        }

    @command("assert")
    @argument("result", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    def aver(self, result: str = 'all'):
        """Assert VXLAN Forwarding is functioning properly"""

        now = time.time()

        df = self._invoke_sqobj(self.sqobj.aver,
                                hostname=self.hostname,
                                namespace=self.namespace,
                                columns=self._add_result_columns(self.columns),
                                result=result,
                                **self.lvars,
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)
