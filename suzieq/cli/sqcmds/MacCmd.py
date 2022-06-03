from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.macs import MacsObj


@command("mac", help="Act on MAC Table data")
@argument("vlan", description="VLAN(s). space separated")
@argument("macaddr",
          description="MAC address(es), in quotes, space separated")
@argument("remoteVtepIp",
          description="Remote VTEP IP(s), space separated; use any for all")
@argument("bd", description="Bridge Domain(s), space separated")
@argument("local", type=bool,
          description="filter entries with no remoteVtep")
@argument("moveCount", description="num of times this MAC has moved")
class MacCmd(SqTableCommand):
    """MAC address table information"""

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
            vlan: str = '',
            macaddr: str = '',
            remoteVtepIp: str = '',
            bd: str = '',
            local: bool = False,
            moveCount: str = ''
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
            sqobj=MacsObj,
        )

        self.lvars = {
            'vlan': vlan.split(),
            'macaddr': macaddr.split(),
            'remoteVtepIp': remoteVtepIp.split(),
            'bd': bd.split(),
            'local': local,
            'moveCount': moveCount
        }
