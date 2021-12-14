import time
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.lldp import LldpObj


@command("lldp", help="Act on LLDP data")
class LldpCmd(SqCommand):
    """LLDP protocol information"""

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
            sqobj=LldpObj,
        )

    @command("show")
    @argument("ifname", description="interface name to qualify")
    @argument("peerHostname", description="peer hostname to filter results")
    @argument("peerMacaddr", description="peer MAC address to filter results")
    def show(self, ifname: str = "", peerHostname: str = "",
             peerMacaddr: str = ""):
        """Show LLDP info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname,
                                ifname=ifname.split(),
                                columns=self.columns,
                                query_str=self.query_str,
                                namespace=self.namespace,
                                peerMacaddr=peerMacaddr.split(),
                                peerHostname=peerHostname.split()
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
