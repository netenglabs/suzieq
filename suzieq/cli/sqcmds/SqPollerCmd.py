import time
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.sqPoller import SqPollerObj


@command("sqPoller", help="Act on SqPoller data", aliases=['sqpoller'])
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
        format: str = "",
        query_str: str = "",
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
            sqobj=SqPollerObj,
        )

    @command("show")
    @argument("service", description="name of service to match")
    @argument("status", description="status of service to match",
              choices=["all", "pass", "fail"])
    @argument('poll_period_exceeded',
              description="filter if poll period exceeded",
              choices=['True', 'False'])
    def show(self, service: str = "", status: str = "all",
             poll_period_exceeded: str = "") -> None:
        """Show Suzieq poller info such as status of polled commands etc.
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        if poll_period_exceeded == "True":
            pollExcdPeriodCount = "!0"
        elif poll_period_exceeded == "False":
            pollExcdPeriodCount = "0"
        else:
            pollExcdPeriodCount = ''
        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname,
                                columns=self.columns,
                                service=service,
                                status=status,
                                namespace=self.namespace,
                                pollExcdPeriodCount=pollExcdPeriodCount,
                                query_str=self.query_str,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
