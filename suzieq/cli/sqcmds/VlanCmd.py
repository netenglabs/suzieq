from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.vlan import VlanObj


@command('vlan', help="Act on vlan data")
@argument("state", description="State of VLAN to query",
          choices=['active', 'suspended'])
@argument("vlan",
          description="VLAN(s), space separated, can use <, >, <=, >=, !")
@argument('vlanName',
          description="VLAN name(s), space separated")
class VlanCmd(SqTableCommand):
    """Information about VLANs including interfaces belonging to a VLAN"""

    # pylint: disable=redefined-builtin
    def __init__(
            self,
            engine: str = '',
            hostname: str = '',
            start_time: str = '',
            end_time: str = '',
            view: str = '',
            namespace: str = '',
            query_str: str = ' ',
            format: str = "",
            columns: str = 'default',
            vlan: str = '',
            vlanName: str = '',
            state: str = '',
    ) -> None:
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, namespace=namespace, query_str=query_str,
                         format=format, columns=columns, sqobj=VlanObj)
        self.lvars = {
            'vlan': vlan.split(),
            'vlanName': vlanName.split(),
            'state': state
        }
