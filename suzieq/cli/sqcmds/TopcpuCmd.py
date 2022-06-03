from nubia import command

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.topcpu import TopcpuObj


@command("topcpu", help="Act on topcpu data")
class TopcpuCmd(SqTableCommand):
    """Information about Top CPU users"""

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
            sqobj=TopcpuObj
        )
