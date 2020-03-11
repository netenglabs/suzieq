import time
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.macs import MacsObj


@command("mac", help="Act on MAC Table data")
class MacCmd(SqCommand):
    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        datacenter: str = "",
        format: str = "",
        columns: str = "default",
    ) -> None:
        super().__init__(
            engine=engine,
            hostname=hostname,
            start_time=start_time,
            end_time=end_time,
            view=view,
            datacenter=datacenter,
            columns=columns,
            format=format,
            sqobj=MacsObj,
        )

    @command("show")
    @argument("vlan", description="VLAN(s) to qualify output")
    @argument("macaddr",
              description="MAC address(es), in quotes, to qualify output")
    @argument("remoteVtepIp", description="only with this remoteVtepIp; use any for all")
    def show(self, vlan: str = '', macaddr: str = '', remoteVtepIp: str = ''):
        """
        Show MAC table info
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
            vlan=vlan.split(),
            macaddr=macaddr.split(),
            remoteVtepIp=remoteVtepIp.split(),
            columns=self.columns,
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("summarize")
    @argument("vlan", description="VLAN(s) to qualify output")
    @argument("macaddr",
              description="MAC address(es), in quotes, to qualify output")
    @argument("remoteVtepIp",
              description="RemoteVtepIps, in quotes, to qualify, use 'any' for all")
    @argument("groupby", description="list of fields to group by")
    def summarize(self, vlan: str = "", macaddr: str = '',
                  remoteVtepIp: str = "", groupby: str = ""):
        """
        Summarize MAC Table info
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
            vlan=vlan.split(),
            macaddr=macaddr.split(),
            groupby=groupby.split(),
            remoteVtepIp=remoteVtepIp.split(),
            datacenter=self.datacenter,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
