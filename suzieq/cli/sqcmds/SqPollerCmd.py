from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.sqPoller import SqPollerObj


@command("sqPoller", help="Act on SqPoller data", aliases=['sqpoller'])
@argument("service", description="name of service to match")
@argument("status", description="status of service to match",
          choices=["all", "pass", "fail"])
@argument('poll_period_exceeded',
          description="filter if poll period exceeded",
          choices=['True', 'False'])
class SqPollerCmd(SqCommand):
    """Information about the poller"""

    def __init__(
            self,
            engine: str = "",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "",
            namespace: str = "",
            format: str = "",  # pylint: disable=redefined-builtin
            query_str: str = "",
            columns: str = "default",
            service: str = '',
            status: str = 'all',
            poll_period_exceeded: str = 'False',
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
            sqobj=SqPollerObj,
        )
        if not poll_period_exceeded or poll_period_exceeded == "False":
            poll_period_exceeded = "0"
        else:
            poll_period_exceeded = "!0"
        self.lvars = {
            'service': service.split(),
            'status': status,
            'pollExcdPeriodCount': poll_period_exceeded,
        }
