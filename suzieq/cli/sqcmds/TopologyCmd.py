import time
import pandas as pd
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.topology import TopologyObj


@command("topology", help="build and act on topology data")
class TopologyCmd(SqCommand):
    """Information about the topology constructed from various protocols"""

    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "",
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
            sqobj=TopologyObj
        )

    @command("show")
    @argument("polled", description="Is the device polled by Suzieq",
              choices=['True', 'False'])
    @argument("ifname", description="interface name to qualify")
    @argument("via", description="filter the method by which topology is seen",
              choices=['arpnd', 'bgp', 'lldp', 'ospf'])
    @argument("peerHostname",
              description="filter the result by specified peerHostname")
    def show(self, polled: str = '', ifname: str = '', via: str = '',
             peerHostname: str = ''):
        """Show table of topology information"""
        # Get the default display field names
        if self.columns is None:
            return

        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                namespace=self.namespace,
                                ifname=ifname.split(),
                                via=via.split(),
                                polled=polled,
                                peerHostname=peerHostname.split(),
                                hostname=self.hostname,
                                query_str=self.query_str,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._gen_output(df)

    @command("summarize")
    @argument("via", description="filter the method by which topology is seen",
              choices=['arpnd', 'bgp', 'lldp', 'ospf'])
    def summarize(self, via: str = ""):
        """Summarize topology information"""
        # Get the default display field names
        if self.columns is None:
            return

        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        try:
            df = self._invoke_sqobj(self.sqobj.summarize,
                                    hostname=self.hostname,
                                    namespace=self.namespace,
                                    via=via.split(),
                                    )
        except Exception as e:
            df = pd.DataFrame({'error': ['ERROR: {}'.format(str(e))]})

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if not df.empty:
            return self._gen_output(df)
