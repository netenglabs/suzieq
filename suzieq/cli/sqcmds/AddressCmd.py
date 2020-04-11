import time

from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.address import AddressObj


@command("address", help="Act on address data")
class AddressCmd(SqCommand):
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
            format=format,
            columns=columns,
            sqobj=AddressObj,
        )

    @command("show")
    @argument("address", description="Address, in quotes, to show info for")
    @argument("ipvers", description="type of address, v4, v6 or l2",
              choices=["v4", "v6", "l2"])
    def show(self, address: str = "", ipvers: str = "v4"):
        """
        Show address info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.sqobj.get(
            hostname=self.hostname,
            columns=self.columns,
            address=address,
            ipvers=ipvers,
            namespace=self.namespace,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
