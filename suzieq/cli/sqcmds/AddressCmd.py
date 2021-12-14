import time

from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.address import AddressObj


@command("address", help="Act on interface addresses")
class AddressCmd(SqCommand):
    """IP and MAC addresses associated with interfaces"""

    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "",
        namespace: str = "",
        format: str = "",  # pylint: disable=redefined-builtin
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
            format=format,
            columns=columns,
            query_str=query_str,
            sqobj=AddressObj,
        )

    @command("show")
    @argument("address",
              description="Address, in quotes, to show info for")
    @argument("prefix",
              description=("Show all the addresses in this "
                           "subnet prefix (in quotes)"))
    @argument("vrf",
              description="VRF to qualify the address")
    @argument("ipvers",
              description="type of address, v4, v6 or l2",
              choices=["v4", "v6", "l2"])
    @argument("type", description="interface type to filter on")
    @argument("ifname", description="interface name to filter on")
    # pylint: disable=redefined-builtin
    def show(self, address: str = "", prefix: str = "",
             ipvers: str = "", vrf: str = "", type: str = "",
             ifname: str = ""):
        """Show address info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname,
                                columns=self.columns,
                                address=address.split(),
                                prefix=prefix.split(),
                                ipvers=ipvers,
                                vrf=vrf.split(),
                                type=type.split(),
                                ifname=ifname.split(),
                                query_str=self.query_str,
                                namespace=self.namespace,
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
