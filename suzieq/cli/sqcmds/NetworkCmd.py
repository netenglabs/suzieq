import ast
import time
from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.network import NetworkObj


@command("network", help="Act on network-wide data")
class NetworkCmd(SqCommand):
    """Advanced commands across all the network"""

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
            sqobj=NetworkObj,
        )

    @command("find", help="find where an IP/MAC address is attached")
    @argument("address", type=str,
              description="IP/MAC addresses, in quotes, space separated")
    @argument("vrf", type=str,
              description="Find within this VRF, used for IP addr")
    @argument("vlan", type=str,
              description="Find MAC within this VLAN")
    def find(self, address: str = '', vrf: str = '',
             vlan: str = ''):
        """Find the network attach point of a given IP or MAC address.
        """
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.find,
                                namespace=self.namespace,
                                hostname=self.hostname,
                                address=address.split(),
                                vlan=vlan,
                                vrf=vrf,
                                query_str=self.query_str,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._gen_output(df)

    @command("show", help="Deprecated. Use 'namespace show' instead")
    @argument("model", description="Device model(s), space separated")
    @argument("os", description='Device NOS(es), space separated')
    @argument('vendor', description='Device vendor(s), space separated')
    @argument('version', description='Device NOS version(s), space separated')
    def show(self, os: str = "", vendor: str = "", model: str = "",
             version: str = "") -> int:
        """Deprecated. Use 'namespace show' instead
        """
        # backward compatibility
        self._print_depracation_command_warning('namespace', 'show')
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.get,
                                namespace=self.namespace, os=os.split(),
                                vendor=vendor.split(), model=model.split(),
                                version=version, query_str=self.query_str,
                                hostname=self.hostname, ignore_warning=True)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._gen_output(df)

    @command("summarize", help="Deprecated. Use 'namespace summarize' instead")
    def summarize(self, **kwargs):
        """Deprecated. Use 'namespace summarize' instead"""
        # backward compatibility
        self._print_depracation_command_warning('namespace', 'summarize')
        now = time.time()

        summarize_df = self._invoke_sqobj(
            self.sqobj.summarize, namespace=self.namespace,
            hostname=self.hostname, query_str=self.query_str,
            ignore_warning=True,
            **self.lvars,
            **kwargs
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(summarize_df, json_orient='columns')

    @command("unique", help="Deprecated. Use 'namespace unique' instead")
    @argument("count", description="include count of times a value is seen",
              choices=['True'])
    def unique(self, count='', **kwargs):
        """Deprecated. Use 'namespace unique' instead"""
        # backward compatibility
        self._print_depracation_command_warning('namespace', 'unique')
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.unique,
                                hostname=self.hostname,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                count=count,
                                ignore_warning=True,
                                **self.lvars,
                                **kwargs,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if 'error' in df.columns:
            return self._gen_output(df)

        if df.empty:
            return df

        if not count:
            return self._gen_output(df.sort_values(by=[df.columns[0]]),
                                    dont_strip_cols=True)
        else:
            return self._gen_output(
                df.sort_values(by=['numRows', df.columns[0]]),
                dont_strip_cols=True)

    @ command("top", help="Deprecated. Use 'namespace top' instead")
    @ argument("count", description="number of rows to return")
    @ argument("what", description="numeric field to get top values for")
    @ argument("reverse", description="return bottom n values",
               choices=['True', 'False'])
    def top(self, count: int = 5, what: str = '', reverse: str = 'False',
            **kwargs) -> int:
        """Deprecated. Use 'namespace top' instead

        Args:
            count (int, optional): Number of entries to return. Defaults to 5
            what (str, optional): Field name to use for largest/smallest val
            reverse (bool, optional): Reverse and return n smallest

        Returns:
            int: 0 or error code
        """
        # backward compatibility
        self._print_depracation_command_warning('namespace', 'top')
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.top,
                                hostname=self.hostname,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                what=what, count=count,
                                reverse=ast.literal_eval(reverse),
                                ignore_warning=True,
                                **self.lvars,
                                **kwargs,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if 'error' in df.columns:
            return self._gen_output(df)

        if not df.empty:
            df = self.sqobj.humanize_fields(df)
            return self._gen_output(df.sort_values(
                by=[what], ascending=(reverse == "True")),
                dont_strip_cols=True, sort=False)
        else:
            return self._gen_output(df)

    @ command("help", help="show help for a command")
    @ argument("command", description="command to show help for",
               choices=['find', 'show', 'summarize', 'top', 'unique'])
    # pylint: disable=redefined-outer-name
    def help(self, command: str = ''):
        return super().help(command)
