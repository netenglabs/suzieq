import time
import re
from nubia import command, argument
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.device import DeviceObj


@command("device", help="Act on device data")
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
            format: str = "",
            query_str: str = " ",
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
            sqobj=DeviceObj,
        )

    def _get(self, **kwargs):
        # Get the default display field names
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname, columns=self.columns,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                **kwargs,
                                )

        df = self.sqobj.humanize_fields(df)

        return df

    @command("show", help="Show device information")
    @argument("os", description="filter by NOS")
    @argument("vendor", description="filter by vendor")
    @argument("model", description="filter by model")
    @argument("version", description="filter by version")
    @argument("status", description="filter by polling status",
              choices=["dead", "alive",  "neverpoll"])
    def show(self, os: str = '', model: str = '', status: str = '',
             vendor: str = '', version: str = ''):
        """Show device info
        """
        if self.columns is None:
            return

        now = time.time()

        # Model has to be special cased because model names can have
        # spaces in them such as "Nexus9000 C9300v Chassis"
        if model:
            model = re.split(r"\s+(?=[^']*(?:'))", model)
        else:
            model = []
        df = self._get(os=os.split(), model=model, version=version,
                       vendor=vendor.split(), status=status.split())

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._gen_output(df)
