import time
from nubia import command, argument
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.fs import FsObj


@command("fs", help="Act on File System data")
class FsCmd(SqCommand):
    def __init__(
        self,
        engine: str = "",
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
            sqobj=FsObj,
        )

    @command("show")
    @argument("mountPoint", description="The mount point inside the FileSystem")
    @argument("used_percent", description="must be of the form "
              "[<|<=|>=|>|!]value. Eg: '<=20'")
    def show(self, mountPoint: str = '', used_percent: str = ''):
        """
        Show File System info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        if used_percent and not any(used_percent.startswith(x)
                                    for x in ['<=', '>=', '<', '>', '!']):
            try:
                int(used_percent)
            except ValueError:
                df = pd.DataFrame(
                    {'error': ['ERROR invalid used-percent operation']})
                return self._gen_output(df)

        df = self.sqobj.get(
            hostname=self.hostname,
            columns=self.columns,
            namespace=self.namespace,
            mountPoint=mountPoint.split(),
            usedPercent=used_percent,
            query_str=self.query_str,
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("summarize")
    def summarize(self):
        """
        Summarize the filesystem/storage info
        """
        df = pd.DataFrame({'error': ['Summarize not yet supported for FS']})
        return self._gen_output(df)
