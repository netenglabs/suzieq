import time
import re
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.inventory import InventoryObj


@command("inventory", help="Act on LLDP data")
class InventoryCmd(SqCommand):
    """Device inventory information such as serial number, cable info etc"""

    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "",
        namespace: str = "",
        format: str = "",
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
            sqobj=InventoryObj,
        )

    @command("show")
    @argument("type", description="Filter by type",
              choices=["fan", "power", "xcvr", "supervisor", "port-adapter", "linecard", "fabric", "midplane", "mx-cb"])
    @argument("status", description="Filter by status",
              choices=['present', 'absent'])
    @argument("model", description="Filter by model")
    @argument("serial", description="Filter by serial number")
    @argument("vendor", description="Filter by vendor name")
    def show(self, type: str = "", status: str = "", model: str = "",
             serial: str = "", vendor: str = "") -> None:
        """Show Device inventory info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        if vendor:
            vendor = re.split(r"\s+(?=[^']*(?:'))", vendor)
        else:
            vendor = []

        if model:
            model = re.split(r"\s+(?=[^']*(?:'))", model)
        else:
            model = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname,
                                columns=self.columns,
                                query_str=self.query_str,
                                type=type.split(),
                                status=status,
                                model=model,
                                vendor=vendor,
                                serial=serial.split(),
                                namespace=self.namespace,
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
