import re
from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.inventory import InventoryObj


@command("inventory", help="Act on inventory data")
@argument("type", description="Filter by type",
          choices=["fan", "power", "xcvr", "supervisor", "port-adapter",
                   "linecard", "fabric", "midplane", "mx-cb"])
@argument("status", description="Filter by status",
          choices=['present', 'absent'])
@argument("model", description="Filter by model")
@argument("serial", description="Serial number(s), space separated")
@argument("vendor", description="Vendor(s), space separated")
class InventoryCmd(SqTableCommand):
    """Device inventory information such as serial number, cable info etc"""

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
            type: str = '',     # pylint: disable=redefined-builtin
            status: str = '',
            model: str = '',
            serial: str = '',
            vendor: str = '',
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

        if vendor:
            vendor = re.split(r"\s+(?=[^']*(?:'))", vendor)
        else:
            vendor = []

        if model:
            model = re.split(r"\s+(?=[^']*(?:'))", model)
        else:
            model = []

        self.lvars = {
            'type': type.split(),
            'status': status,
            'model': model,
            'vendor': vendor,
            'serial': serial,
        }
