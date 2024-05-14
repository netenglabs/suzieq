from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.igmp import IgmpObj


@command("igmp", help="Act on Igmp")
@argument("vrf", description="VRF(s), space separated")
@argument("group", description="Group(s), in quotes, space separated")
class IgmpCmd(SqTableCommand):
    """IGMP table information"""

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
            group: str = "",
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
            sqobj=IgmpObj,
        )
        self.lvars = {
            'vrf': vrf.split(),
            'group': group.split()
        }
