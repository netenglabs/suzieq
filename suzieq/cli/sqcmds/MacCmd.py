import time
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.macs import MacsObj


@command("mac", help="Act on MAC Table data")
class MacCmd(SqCommand):
    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "latest",
        namespace: str = "",
        format: str = "",
        query_str: str = ' ',
        columns: str = "default",
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

    @command("show")
    @argument("vlan", description="VLAN(s) to qualify output")
    @argument("macaddr",
              description="MAC address(es), in quotes, to qualify output")
    @argument("remoteVtepIp", description="only with this remoteVtepIp; use any for all")
    @argument("bd", description="filter entries with this bridging domain")
    @argument("local", description="filter entries with no remoteVtep")
    @argument("moveCount", description="num of times this MAC has moved")
    def show(self, vlan: str = '', macaddr: str = '', remoteVtepIp: str = '',
             bd: str = '', local: bool = False, moveCount: str = ''):
        """Show MAC table info

        The remoteVtepInfo is set to "-" to allow to fetch local entries only
        """
        if self.columns is None:
            return

        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        drop_cols = []

        if vlan and (self.columns != ['default'] and self.columns != ['*'] and
                     'vlan' not in self.columns):
            addnl_fields = ['vlan']
            drop_cols.append('vlan')
        else:
            addnl_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname,
                                macaddr=macaddr.split(),
                                addnl_fields=addnl_fields,
                                remoteVtepIp=remoteVtepIp.split(),
                                vlan=vlan.split(),
                                localOnly=local,
                                bd=bd,
                                columns=self.columns,
                                namespace=self.namespace,
                                moveCount=moveCount,
                                query_str=self.query_str,
                                )
        if not df.empty and "mackey" in df.columns:
            drop_cols.append('mackey')

        df.drop(columns=drop_cols, inplace=True)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)
