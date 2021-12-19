import re
from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.device import DeviceObj


@command("device", help="Act on device data")
@argument("status", description="filter by polling status",
          choices=["dead", "alive",  "neverpoll"])
@argument("os", description="filter by NOS")
@argument("version", description="filter by NOS version")
@argument("vendor", description="filter by vendor")
@argument("model", description="filter by model")
class DeviceCmd(SqCommand):
    """Basic device information such as OS, version, model etc."""

    def __init__(
            self,
            engine: str = "",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "",
            namespace: str = "",
            format: str = "",  # pylint: disable=redefined-builtin
            query_str: str = " ",
            columns: str = "default",
            os: str = '',
            version: str = '',
            status: str = '',
            vendor: str = '',
            model: str = '',
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
            sqobj=DeviceObj,
        )
        if model:
            model = re.split(r"\s+(?=[^']*(?:'))", model)

        self.lvars = {
            'os': os.split(),
            'version': version.split(),
            'status': status,
            'model': model,
            'vendor': vendor.split()
        }
