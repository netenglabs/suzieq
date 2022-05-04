from nubia import command

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.topmem import TopmemObj


@command("topmem", help="Act on topmem data")
class TopmemCmd(SqTableCommand):
    '''The CLI command providing access to the topmem table'''

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
            sqobj=TopmemObj,
        )
