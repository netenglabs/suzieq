from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.address import AddressObj


@argument("vrf",
          description="VRF to qualify the address")
@argument("type", description="interface type to filter on")
@argument("ifname", description="interface name to filter on")
@argument("ipvers",
          description="type of address, v4, v6 or l2",
          choices=["v4", "v6", "l2"])
@argument("address",
          description="Address, in quotes, to show info for")
@argument("prefix",
          description=("Show all the addresses in this "
                       "subnet prefix (in quotes)"))
@command("address", help="Act on interface addresses")
class AddressCmd(SqCommand):
    """IP and MAC addresses associated with interfaces"""

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
            vrf: str = '',
            type: str = '',     # pylint: disable=redefined-builtin
            ifname: str = '',
            ipvers: str = '',
            address: str = '',
            prefix: str = '',
    ) -> None:
        super().__init__(
            engine=engine,
            hostname=hostname,
            start_time=start_time,
            end_time=end_time,
            view=view,
            namespace=namespace,
            format=format,
            columns=columns,
            query_str=query_str,
            sqobj=AddressObj,
        )
        self.lvars = {
            'vrf': vrf.split(),
            'type': type.split(),
            'ifname': ifname.split(),
            'ipvers': ipvers,
            'address': address.split(),
            'prefix': prefix.split()
        }
