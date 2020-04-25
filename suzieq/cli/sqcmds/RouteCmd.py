import time
import ipaddress
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.routes import RoutesObj


@command("route", help="Act on Routes")
class RouteCmd(SqCommand):
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
            sqobj=RoutesObj,
        )
        self.json_print_handler = self._json_print_handler

    def _json_print_handler(self, input):
        """This handler calls the code to print the IPNetwork as a string"""
        if isinstance(input, ipaddress.IPv4Network):
            return ipaddress.IPv4Network.__str__(input)
        elif isinstance(input, ipaddress.IPv6Network):
            return ipaddress.IPv6Network.__str__(input)
        return input

    def _get_ipvers(self, value: str) -> int:
        """Return the IP version in use"""

        if ':' in value:
            ipvers = 6
        elif '.' in value:
            ipvers = 4
        else:
            ipvers = None

        return ipvers

    @command("show")
    @argument("prefix", description="Prefix, in quotes, to filter show on")
    @argument("vrf", description="VRF to qualify")
    @argument("protocol", description="routing protocol to qualify")
    def show(self, prefix: str = "", vrf: str = '', protocol: str = ""):
        """
        Show Routes info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns == ['*']:
            remove_metric = False
        elif self.columns != ["default"]:
            self.ctxt.sort_fields = None
            if 'metric' not in self.columns:
                self.columns.append('metric')
                remove_metric = True
        else:
            self.ctxt.sort_fields = []
            remove_metric = False

        # /32 routes are stored with the /32 prefix, so if user doesn't specify
        # prefix as some folks do, assume /32
        ipvers = self._get_ipvers(prefix)

        if prefix and '/' not in prefix:
            if ipvers == 4:
                prefix += '/32'
            else:
                prefix += '/128'

        df = self.sqobj.get(
            hostname=self.hostname,
            prefix=prefix.split(),
            vrf=vrf.split(),
            protocol=protocol.split(),
            ipvers=ipvers,
            columns=self.columns,
            namespace=self.namespace,
        )
        if not df.empty and remove_metric:
            df.drop(columns=['metric'], inplace=True)
            self.columns.remove('metric')

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command('lpm')
    @argument("address", description="IP Address, in quotes, for lpm query")
    @argument("vrf", description="specific VRF to qualify")
    def lpm(self, address: str = "", vrf: str = "default"):
        """
        Show the Longest Prefix Match on a given prefix, vrf
        """
        if self.columns is None:
            return

        now = time.time()
        if self.columns == ['*']:
            remove_metric = False
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
            if 'metric' not in self.columns:
                self.columns.append('metric')
                remove_metric = True
        else:
            self.ctxt.sort_fields = []
            remove_metric = False

        if not address:
            print('address is mandatory parameter')
            return

        df = self.sqobj.lpm(
            hostname=self.hostname,
            address=address,
            vrf=vrf.split(),
            ipvers=self._get_ipvers(address),
            columns=self.columns,
            namespace=self.namespace,
        )

        if not df.empty and remove_metric:
            df.drop(columns=['metric'], inplace=True)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
