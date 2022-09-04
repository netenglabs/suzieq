from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.path import PathObj


@command("path", help="build and act on path data")
@argument("src", description="Source IP address, in quotes")
@argument("dest", description="Destination IP address, in quotes")
@argument("vrf", description="VRF to trace path in")
class PathCmd(SqTableCommand):
    """Path trace information including overlay and underlay"""

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
        src: str = "",
        dest: str = "",
        vrf: str = "",
        query_str: str = ' ',
    ) -> None:
        super().__init__(
            engine=engine,
            hostname=hostname,
            start_time=start_time,
            end_time=end_time,
            view=view,
            namespace=namespace,
            columns=columns,
            query_str=query_str,
            format=format,
            sqobj=PathObj
        )
        self.lvars = {
            'src': src,
            'dest': dest,
            'vrf': vrf
        }
