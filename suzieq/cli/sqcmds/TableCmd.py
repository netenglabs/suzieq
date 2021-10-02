import time

from nubia import command, argument
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.tables import TablesObj


@command("table", help="Information about the various tables")
class TableCmd(SqCommand):
    """Meta information about the various data gathered"""

    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "",
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
            sqobj=TablesObj,
        )

    @command("show")
    def show(self, **kwargs):
        """Show meta-information about various tables gathered by Suzieq
        """
        now = time.time()
        df = self.sqobj.get(hostname=self.hostname, namespace=self.namespace,
                            columns=self.columns)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @ command("describe")
    @ argument("table", description="interface name to qualify")
    def describe(self, table: str = "tables", **kwargs):
        """
        Describe fields in table
        """

        if not table:
            df = pd.DataFrame({'error': ['ERROR: Must specify a table']})
            return self._gen_output(df)

        if self.columns != ['default']:
            df = pd.DataFrame(
                {'error': ['ERROR: Cannot specify columns for command']})
            return self._gen_output(df)

        now = time.time()
        df = self.sqobj.describe(table=table)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._gen_output(df, dont_strip_cols=True)
