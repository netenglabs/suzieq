import time
from nubia import command, argument
import pandas as pd

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.interfaces import IfObj
from suzieq.utils import humanize_timestamp


@command("interface", help="Act on Interface data")
class InterfaceCmd(SqCommand):
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
            sqobj=IfObj
        )

    @command("show")
    @argument("ifname", description="interface name to qualify")
    @argument("type", description="interface type to qualify")
    @argument("state", description="interface state to qualify show",
              choices=["up", "down"])
    @argument("mtu", description="filter interfaces with MTU")
    def show(self, ifname: str = "", state: str = "", type: str = "",
             mtu: str = ""):
        """
        Show interface info
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
            ifname=ifname.split(),
            columns=self.columns,
            namespace=self.namespace,
            state=state,
            mtu=mtu.split(),
            type=type.split(),
        )
        if 'statusChangeTimestamp' in df.columns:
            df['statusChangeTimestamp'] = humanize_timestamp(
                df.statusChangeTimestamp)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("assert")
    @argument("ifname", description="interface name to qualify")
    @argument(
        "what",
        description="What do you want to assert",
        choices=["mtu-match", "mtu-value"],
    )
    @argument("value", description="Value to match against")
    @argument("status", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    def aver(self, ifname: str = "", state: str = "", what: str = "mtu-match",
             value: int = 0, status: str = 'all'):
        """
        Assert aspects about the interface
        """
        if self.columns != ["default"]:
            df = pd.DataFrame(
                {'error': ['ERROR: You cannot specify columns with assert']})
            return self._gen_output(df)

        now = time.time()

        if what == "mtu-value" and value == 0:
            print("Provide value to match MTU against")
            return

        if what == "mtu-match":
            value = 0

        try:
            df = self.sqobj.aver(
                hostname=self.hostname,
                ifname=ifname.split(),
                namespace=self.namespace,
                what=what,
                matchval=value,
                status=status,
            )
        except Exception as e:
            df = pd.DataFrame({'error': ['ERROR: {}'.format(str(e))]})
            return self._gen_output(df)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)

    @command("top")
    @argument("what", description="Field you want to see top for",
              choices=["flaps"])
    @argument("count", description="How many top entries")
    @argument("reverse", description="True see Bottom n",
              choices=["True", "False"])
    def top(self, what: str = "flaps", count: int = 5, reverse: str = "False"):
        """
        Show top n entries based on specific field
        """
        if self.columns is None:
            return

        now = time.time()

        if what == "flaps":
            whatfld = "numChanges"

        df = self.sqobj.top(
            hostname=self.hostname,
            what=whatfld,
            n=count,
            reverse=reverse == "True" or False,
            type="ethernet",        # need this as we only do phy interfaces
            columns=self.columns,
            namespace=self.namespace,
        )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df, sort=False)
