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
        query_str: str = ' ',
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

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname,
                                ifname=ifname.split(),
                                columns=self.columns,
                                namespace=self.namespace,
                                state=state,
                                mtu=mtu.split(),
                                query_str=self.query_str,
                                type=type.split(),
                                )
        if 'statusChangeTimestamp' in df.columns:
            df['statusChangeTimestamp'] = humanize_timestamp(
                df.statusChangeTimestamp,
                self.cfg.get('analyzer', {}).get('timezone', None))

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("assert")
    @argument("ifname", description="interface name to qualify")
    @argument(
        "what",
        description="What do you want to assert",
        choices=["mtu-value"],
    )
    @argument("value", description="Value to match against")
    @argument("status", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    def aver(self, ifname: str = "", state: str = "", what: str = "",
             value: str = '', status: str = 'all'):
        """
        Assert aspects about the interface
        """
        if self.columns != ["default"]:
            df = pd.DataFrame(
                {'error': ['ERROR: You cannot specify columns with assert']})
            return self._gen_output(df)

        now = time.time()

        if what == "mtu-value" and value == '':
            print("Provide value to match MTU against")
            return
        elif not what:
            value = ''

        df = self._invoke_sqobj(self.sqobj.aver,
                                hostname=self.hostname,
                                ifname=ifname.split(),
                                namespace=self.namespace,
                                what=what,
                                matchval=value.split(),
                                status=status,
                                )

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

        df = self._invoke_sqobj(self.sqobj.top,
                                hostname=self.hostname,
                                what=whatfld,
                                n=count,
                                reverse=reverse == "True" or False,
                                type="ethernet",        # phy interfaces only
                                columns=self.columns,
                                query_str=self.query_str,
                                namespace=self.namespace,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df, sort=False)
