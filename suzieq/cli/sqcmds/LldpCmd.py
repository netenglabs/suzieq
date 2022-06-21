from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.lldp import LldpObj


@command("lldp", help="Act on LLDP data")
@argument("ifname", description="Interface name(s), space separated")
@argument("peerHostname", description="Peer hostname(s), space separated")
@argument("peerMacaddr", description="Peer mac address(es), space separated")
class LldpCmd(SqTableCommand):
    """LLDP protocol information"""

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
            ifname: str = '',
            peerHostname: str = '',
            peerMacaddr: str = ''
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
            sqobj=LldpObj,
        )
        self.lvars = {
            'peerHostname': peerHostname.split(),
            'ifname': ifname.split(),
            'peerMacaddr': peerMacaddr.split(),
        }
