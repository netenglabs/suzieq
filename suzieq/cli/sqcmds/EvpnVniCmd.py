import time
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.evpnVni import EvpnvniObj


@command("evpnVni", help="Act on EVPN VNI data")
class EvpnVniCmd(SqCommand):
    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        namespace: str = "",
        format: str = "",
        query_str: str = " ",
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
            sqobj=EvpnvniObj,
        )

    @command("show")
    @argument("vni", description="VNI ID to qualify")
    def show(self, vni: str = ""):
        """
        Show EVPN VNI info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname,
                                vni=vni.split(),
                                columns=self.columns,
                                query_str=self.query_str,
                                namespace=self.namespace,
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("assert")
    @argument("status", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    def aver(self, status: str = 'pass'):
        """Assert BGP is functioning properly"""

        now = time.time()

        df = self._invoke_sqobj(self.sqobj.aver,
                                hostname=self.hostname,
                                namespace=self.namespace,
                                status=status,
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)
