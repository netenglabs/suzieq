import time
from nubia import command, argument
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.devconfig import DevconfigObj


@command("devconfig", help="Act on device data")
class DevconfigCmd(SqCommand):
    """device command"""

    def __init__(
            self,
            engine: str = "pandas",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "latest",
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
            sqobj=DevconfigObj,
        )

    @command("show", help="Show device information")
    def show(self):
        """
        Show device config info
        """
        if self.columns is None:
            return

        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname, columns=self.columns,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        if not self.format or (self.format == 'text'):
            self.format = 'devconfig'
        return self._gen_output(df)

    @command("unique", help="Show unique information about columns")
    def unique(self):
        """
        Unique device config info
        """

        df = pd.DataFrame(
            {'error': ['Unique not supported for Device Config']})
        return self._gen_output(df)
