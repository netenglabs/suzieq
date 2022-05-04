from nubia import command
import pandas as pd

from suzieq.cli.nubia_patch import argument
from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.fs import FsObj


@command("fs", help="Act on File System data")
@argument("used_percent", description="must be of the form "
          "[<|<=|>=|>|!]value. Eg: '<=20'")
@argument("mountPoint", description="Mount point(s), space separated")
class FsCmd(SqTableCommand):
    """Filesystem information such as total disk space, filesystems etc"""

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
            used_percent: str = '',
            mountPoint: str = ''
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
        self.lvars = {
            'usedPercent': used_percent,
            'mountPoint': mountPoint.split()
        }

    @command("show")
    def show(self):
        """Show File System info
        """
        # Get the default display field names
        used_percent = self.lvars.get('usedPercent')
        if used_percent and not any(used_percent.startswith(x)
                                    for x in ['<=', '>=', '<', '>', '!']):
            try:
                int(used_percent)
            except ValueError:
                df = pd.DataFrame(
                    {'error': ['ERROR invalid used-percent operation']})
                return self._gen_output(df)

        return super().show()

    @command("summarize")
    def summarize(self, **kwargs):
        """
        Summarize the filesystem/storage info
        """
        df = pd.DataFrame({'error': ['Summarize not yet supported for FS']})
        return self._gen_output(df)
