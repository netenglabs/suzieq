from nubia import command, argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.devconfig import DevconfigObj


@command("devconfig", help="Act on device data")
@argument("section",
          description="show device config only for this regex match")
class DevconfigCmd(SqTableCommand):
    """Device configurations"""

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
            section: str = '',
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

        self.lvars['section'] = section

    @command("show", help="Show device information")
    def show(self):
        """Show device config info
        """
        if not self.format or (self.format == 'text'):
            self.format = 'markdown'
        return super().show()
