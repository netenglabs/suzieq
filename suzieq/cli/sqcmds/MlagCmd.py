import time

from nubia import command

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.mlag import MlagObj


@command('mlag', help="Act on mlag data")
class MlagCmd(SqCommand):

    def __init__(self, engine: str = '', hostname: str = '',
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', namespace: str = '',
                 query_str: str = ' ',
                 format: str = "", columns: str = 'default') -> None:
        super().__init__(engine=engine, hostname=hostname,
                         start_time=start_time, end_time=end_time,
                         view=view, namespace=namespace,
                         format=format, query_str=query_str, columns=columns,
                         sqobj=MlagObj)

    @command('show')
    def show(self):
        """
        Show mlag info
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
                                hostname=self.hostname,
                                columns=self.columns, query_str=self.query_str,
                                namespace=self.namespace)
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if not df.empty and 'state' in df.columns:
            return self._gen_output(df.query('state != "disabled"'))
        else:
            return self._gen_output(df)
