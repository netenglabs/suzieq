import time
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.arpnd import ArpndObj


@command("arpnd", help="Act on ARP/ND data")
class ArpndCmd(SqCommand):
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
        query_str: str = ' ',
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
            sqobj=ArpndObj,
        )

    @command("show")
    @argument("address", description="IP address, in quotes, to qualify output")
    @argument("macaddr", description="MAC address, in quotes, to qualify output")
    @argument("oif", description="outgoing interface to qualify")
    def show(self, address: str = "", macaddr: str = '', oif: str = ''):
        """
        Show ARP/ND info
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
                                ipAddress=address.split(),
                                oif=oif.split(),
                                columns=self.columns,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                macaddr=macaddr.split()
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
