from nubia import command
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.devconfig import DevconfigObj


@command("devconfig", help="Act on device data")
class DevconfigCmd(SqCommand):
    """Device configurations"""

    def __init__(
            self,
            engine: str = "pandas",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "",
            namespace: str = "",
            format: str = "",  # pylint: disable=redefined-builtin
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
        """Show device config info
        """
        if not self.format or (self.format == 'text'):
            self.format = 'devconfig'
        return super().show()

    @command("unique", help="Show unique information about columns")
    def unique(self, **kwargs):  # pylint: disable=arguments-differ
        """
        Unique device config info
        """

        df = pd.DataFrame(
            {'error': ['Unique not supported for Device Config']})
        return self._gen_output(df)
