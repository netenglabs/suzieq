from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.macs import MacsObj


@command("mac", help="Act on MAC Table data", aliases=['macs'])
@argument("vlan", description="VLAN(s) to qualify output")
@argument("macaddr",
          description="MAC address(es), in quotes, to filter")
@argument("remoteVtepIp",
          description="only with this remoteVtepIp; use any for all")
@argument("bd", description="filter entries with this bridging domain")
@argument("local", type=bool,
          description="filter entries with no remoteVtep")
@argument("moveCount", description="num of times this MAC has moved")
class MacCmd(SqCommand):
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
