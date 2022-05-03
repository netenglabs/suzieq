import time
import ipaddress
import pandas as pd

from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.routes import RoutesObj


@command("route", help="Act on Routes")
@argument("vrf", description="VRF(s), space separated")
@argument("protocol", description="Routing protocol(s), space separated")
@argument("prefix", description="Prefix(es), in quotes, space separated")
@argument("prefixlen", description="must be of the form "
          "[<|<=|>=|>|!] length")
class RouteCmd(SqTableCommand):
    """Routing table information"""

    def __init__(
            self,
            engine: str = "",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "",
            namespace: str = "",
            format: str = "",  # pylint: disable=redefined-builtin
            query_str: str = ' ',
            columns: str = "default",
            vrf: str = "",
            protocol: str = "",
            prefix: str = '',
            prefixlen: str = '',
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
            sqobj=RoutesObj,
        )
        self.lvars = {
            'protocol': protocol.split(),
            'vrf': vrf.split(),
            'prefix': prefix.split(),
            'prefixlen': prefixlen
        }

    def _json_print_handler(self, in_data):  # pylint: disable=method-hidden
        """This handler calls the code to print the IPNetwork as a string"""
        if isinstance(in_data, ipaddress.IPv4Network):
            return ipaddress.IPv4Network.__str__(in_data)
        elif isinstance(in_data, ipaddress.IPv6Network):
            return ipaddress.IPv6Network.__str__(in_data)
        return in_data

    def _get_ipvers(self, value: str) -> int:
        """Return the IP version in use"""

        if ':' in value:
            ipvers = 6
        elif '.' in value:
            ipvers = 4
        else:
            ipvers = ''

        return ipvers

    @command('lpm')
    @argument("address", description="IP Address, in quotes, for lpm query")
    def lpm(self, address: str = ''):
        """Show the Longest Prefix Match(LPM) on a given prefix, vrf
        """
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        if not address:
            df = pd.DataFrame({'error': ['Must specify address for lpm']})
            return self._gen_output(df)

        df = self._invoke_sqobj(self.sqobj.lpm,
                                hostname=self.hostname,
                                address=address,
                                ipvers=self._get_ipvers(address),
                                columns=self.columns,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                **self.lvars
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
