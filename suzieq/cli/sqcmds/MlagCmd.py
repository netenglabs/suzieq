from nubia import command

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.mlag import MlagObj


@command('mlag', help="Act on mlag data")
class MlagCmd(SqTableCommand):
    """Multichassis LAG information (includes variants such as NXOX vPC)"""

    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = '', namespace: str = '',
                 query_str: str = ' ',
                 format: str = "", columns: str = 'default') -> None:
        # pylint: disable=redefined-builtin
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, namespace=namespace,
                         format=format, query_str=query_str, columns=columns,
                         sqobj=MlagObj)
