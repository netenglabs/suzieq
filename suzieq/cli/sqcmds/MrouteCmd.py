import time
import ipaddress
import pandas as pd

from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.mroutes import MroutesObj


@command("mroute", help="Act on Mroutes")
@argument("vrf", description="VRF(s), space separated")
@argument("source", description="Source(s), in quotes, space separated")
@argument("group", description="Group(s), in quotes, space separated")
class MrouteCmd(SqCommand):
    """Multicast Routing table information"""

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
            source: str = '',
            group: str = '',
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
            sqobj=MroutesObj,
        )
        self.lvars = {
            'vrf': vrf.split(),
            'source': source.split(),
            'group': group.split()
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

    