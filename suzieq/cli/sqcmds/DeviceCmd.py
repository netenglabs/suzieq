import shlex
from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.device import DeviceObj


@command("device", help="Act on device data")
@argument("status", description="filter by polling status",)
@argument("os", description="NOS(s), space separated")
@argument("version", description="NOS version(s), space separated")
@argument("vendor", description="Vendor(s), space separated")
@argument("model", description="Model(s), space separated")
class DeviceCmd(SqTableCommand):
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

        # Nubia eats up the first and last quote. Detect and add back
        model = model.strip()
        if model.count("'") % 2 != 0:
            if not model.startswith("'"):
                model = f"'{model}"
            elif not model.endswith("'"):
                model = f"{model}'"
        if model:
            model = shlex.split(model)

        self.lvars = {
            'os': os.split(),
            'version': version.split(),
            'status': status.split(),
            'model': model,
            'vendor': vendor.split()
        }
