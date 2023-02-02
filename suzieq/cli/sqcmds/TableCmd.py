from nubia import command

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
