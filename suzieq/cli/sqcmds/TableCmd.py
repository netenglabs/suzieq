import time

from nubia import command, argument
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.tables import TablesObj


@command("table", help="Information about the various tables")
class TableCmd(SqCommand):
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
            sqobj=TablesObj,
        )

    @command("show")
    def show(self, **kwargs):
        """
        Show Tables
        """
        now = time.time()
        df = self.sqobj.get(hostname=self.hostname, namespace=self.namespace)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("describe")
    @argument("table", description="interface name to qualify")
    def describe(self, table: str = "", **kwargs):
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

    @command("summarize", help="Summarize info about this resource")
    def summarize(self, **kwargs):

        msg = 'ERROR: Summarize not supported for this object'
        df = pd.DataFrame({'error': [msg]})
        return self._gen_output(df, dont_strip_cols=True)

    @command("unique", help="find the list of unique items in a column")
    def unique(self, **kwargs):

        msg = 'ERROR: Unique not supported for this object'
        df = pd.DataFrame({'error': [msg]})
        return self._gen_output(df, dont_strip_cols=True)
