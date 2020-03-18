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

        df = self.sqobj.get(
            hostname=self.hostname,
            vni=vni.split(),
            columns=self.columns,
            namespace=self.namespace,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("summarize")
    @argument("vni", description="VNI ID to qualify")
    @argument("groupby", description="Space separated list of fields to summarize on")
    def summarize(self, vni: str = "", groupby: str = ""):
        """
        Summarize EVPN VNI info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.sqobj.summarize(
            hostname=self.hostname,
            vni=vni.split(),
            columns=self.columns,
            groupby=groupby.split(),
            namespace=self.namespace,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
