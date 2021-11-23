import time

from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.interfaces import IfObj
from suzieq.utils import humanize_timestamp


@command("interface", help="Act on Interface data", aliases=['interfaces'])
class InterfaceCmd(SqCommand):
    """Device interface information including MTU, Speed, IP address etc"""

    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "",
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
              choices=["up", "down", "notConnected", "!up", "!down",
                       "!notConnected"])
    @argument("mtu", description="filter interfaces with MTU")
    @argument("vrf", description="filter interfaces matching VRFs")
    def show(self, ifname: str = "", state: str = "", type: str = "",
             mtu: str = "", vrf: str = "") -> None:
        """Show interface info
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
                                vrf=vrf.split(),
                                query_str=self.query_str,
                                type=type.split(),
                                )
        if 'statusChangeTimestamp' in df.columns:
            df['statusChangeTimestamp'] = humanize_timestamp(
                df.statusChangeTimestamp,
                self.cfg.get('analyzer', {}).get('timezone', None))

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("unique", help="find the list of unique items in a column")
    @argument("count", description="include count of times a value is seen",
              choices=['True'])
    @argument("type", description="include type of ports to include")
    def unique(self, count: str = '', type: str = '', **kwargs):
        """Get unique values (and counts) associated with requested field"""
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.unique,
                                hostname=self.hostname,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                type=type.split(),
                                addnl_fields=['type'],
                                count=count,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if 'error' in df.columns:
            return self._gen_output(df)

        if not count or df.empty:
            return self._gen_output(df.sort_values(by=[df.columns[0]]),
                                    dont_strip_cols=True)
        else:
            return self._gen_output(
                df.sort_values(by=['numRows', df.columns[0]]),
                dont_strip_cols=True)

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
    @argument("ignore_missing_peer",
              description="Treat missing peer as passing assert check",
              choices=["True", "False"])
    def aver(self, ifname: str = "", state: str = "", what: str = "",
             value: str = '', status: str = 'all',
             ignore_missing_peer: str = "False"):
        """Assert aspects about the interface
        """

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
                                ignore_missing_peer=(
                                    ignore_missing_peer == "True"),
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)

    @command("top", help="Top for any given field")
    @argument("what", description="Field you want to see top for")
    @argument("count", description="How many top entries")
    @argument("reverse", description="True see Bottom n",
              choices=["True", "False"])
    @argument("type", description="interface type to qualify")
    @argument('ifname', description="Interface name to qualify")
    def top(self, what: str = "", count: int = 5, reverse: str = "False",
            ifname: str = '', type: str = 'ethernet'):
        """Show top n entries based on specific field
        """
        if self.columns is None:
            return

        now = time.time()

        df = self._invoke_sqobj(self.sqobj.top,
                                hostname=self.hostname,
                                what=what,
                                count=count,
                                ifname=ifname.split(),
                                reverse=(reverse == "True") or False,
                                type=type.split(),        # phy interfaces only
                                columns=self.columns,
                                query_str=self.query_str,
                                namespace=self.namespace,
                                )

        if 'statusChangeTimestamp' in df.columns:
            df['statusChangeTimestamp'] = humanize_timestamp(
                df.statusChangeTimestamp,
                self.cfg.get('analyzer', {}).get('timezone', None))

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df, sort=False)
