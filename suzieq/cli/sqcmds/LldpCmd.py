import time
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.lldp import LldpObj


@command("lldp", help="Act on LLDP data")
class LldpCmd(SqCommand):
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
            sqobj=LldpObj,
        )

    @command("show")
    @argument("ifname", description="interface name to qualify")
    def show(self, ifname: str = ""):
        """
        Show LLDP info
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
            ifname=ifname.split(),
            columns=self.columns,
            namespace=self.namespace,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("summarize")
    @argument("ifname", description="interface name to qualify")
    @argument("groupby", description="Space separated list of fields to summarize on")
    def summarize(self, ifname: str = "", groupby: str = ""):
        """
        Summarize LLDP info
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
            ifname=ifname.split(),
            columns=self.columns,
            groupby=groupby.split(),
            namespace=self.namespace,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
