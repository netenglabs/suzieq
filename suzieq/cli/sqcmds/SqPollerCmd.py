import time
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.sqPoller import SqPollerObj


@command("sqpoller", help="Act on SqPoller data")
class SqPollerCmd(SqCommand):
    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        namespace: str = "",
        format: str = "",
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
            sqobj=SqPollerObj,
        )

    @command("show")
    @argument("service", description="name of service to match")
    @argument("status", description="status of service to match",
              choices=["all", "pass", "fail"])
    def show(self, service: str = "", status: str = "all"):
        """
        Show SqPoller info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self.sqobj.get(
            hostname=self.hostname,
            columns=self.columns,
            service=service,
            status=status,
            namespace=self.namespace,
        )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
