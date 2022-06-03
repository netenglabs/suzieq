import time

import pandas as pd
from nubia import command

from suzieq.cli.nubia_patch import argument
from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.tables import TablesObj


@command('table', help='get data about data captured for various tables')
class TableCmd(SqTableCommand):
    """Meta information about the various data gathered"""

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

    @ command("describe")
    @ argument("table", description="interface name to qualify")
    def describe(self, table: str = "tables"):
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
