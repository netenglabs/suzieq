import time
from nubia import command, argument
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.device import DeviceObj


@command("device", help="Act on device data")
class DeviceCmd(SqCommand):
    """device command"""

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
            columns=columns,
            format=format,
            sqobj=DeviceObj,
        )

    @command("show", help="Show device information")
    def show(self):
        """
        Show device info
        """
        if self.columns is None:
            return

        now = time.time()
        # Get the default display field names
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        if 'uptime' in self.columns:
            self.columns = ['bootupTimestamp' if x == 'uptime' else x
                            for x in self.columns]
        df = self.sqobj.get(
            hostname=self.hostname, columns=self.columns,
            namespace=self.namespace,
        )
        # Convert the bootup timestamp into a time delta
        if not df.empty and 'bootupTimestamp' in df.columns:
            uptime_cols = (df['timestamp'] -
                           pd.to_datetime(df['bootupTimestamp']*1000,
                                          unit='ms'))
            uptime_cols = pd.to_timedelta(uptime_cols, unit='ms')
            df.insert(len(df.columns)-1, 'uptime', uptime_cols)
            df = df.drop(columns=['bootupTimestamp'])

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

