from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.arpnd import ArpndObj


@command("arpnd", help="Act on ARP/ND data")
@argument("prefix",
          description=("Show all the addresses in this "
                       "subnet prefix (in quotes)"))
@argument("address",
          description="IP Address(es), in quotes, space separated")
@argument("macaddr",
          description="MAC address(es), in quotes, space separated")
@argument("oif", description="Outgoing interface(s), space separated")
class ArpndCmd(SqTableCommand):
    """ARP/Neighbor Discovery information"""

    def __init__(
            self,
            engine: str = "",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "",
            namespace: str = "",
            format: str = "",  # pylint: disable=redefined-builtin
            columns: str = "default",
            query_str: str = ' ',
            prefix: str = '',
            address: str = '',
            macaddr: str = '',
            oif: str = '',
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
            sqobj=ArpndObj,
        )
        self.lvars = {
            'prefix': prefix.split(),
            'ipAddress': address.split(),
            'macaddr': macaddr.split(),
            'oif': oif.split(),
        }
