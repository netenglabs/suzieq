import time

from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.vlan import VlanObj


@command('vlan', help="Act on vlan data")
class VlanCmd(SqCommand):

    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', namespace: str = '',
                 query_str: str = ' ',
                 format: str = "", columns: str = 'default') -> None:
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, namespace=namespace, query_str=query_str,
                         format=format, columns=columns, sqobj=VlanObj)

    @command('show')
    @argument("vlan", description="Space separated list of vlan IDs to show")
    @argument('vlanName',
              description="Space separated list of VLAN names to show")
    @argument("state", description="State of VLAN to query",
              choices=['active', 'suspended'])
    def show(self, vlan: str = '', vlanName: str = '', state: str = ''):
        """
        Show vlan info
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ['default']:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname, vlan=vlan.split(),
                                state=state, vlanName=vlanName.split(),
                                query_str=self.query_str,
                                columns=self.columns, namespace=self.namespace)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
