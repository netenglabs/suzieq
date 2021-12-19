import time
from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqCommand
from suzieq.sqobjects.network import NetworkObj


@command("network", help="Act on network-wide data")
class NetworkCmd(SqCommand):
    """Overall network information such as namespaces present etc."""

    def __init__(
            self,
            engine: str = "",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "",
            namespace: str = "",
            format: str = "",  # pylint: disable=redefined-builtin
            query_str: str = " ",
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
            sqobj=NetworkObj,
        )

    @command("show", help="Show device information")
    @argument("model", description="models to filter with")
    @argument("os", description='NOS to filter with')
    @argument('vendor', description='vendor to filter with')
    @argument('version', description='NOS version to filter with')
    # pylint: disable=arguments-differ
    def show(self, os: str = "", vendor: str = "", model: str = "",
             version: str = "") -> int:
        """Show network info
        """

        now = time.time()

        df = self._invoke_sqobj(self.sqobj.get,
                                namespace=self.namespace, os=os.split(),
                                vendor=vendor.split(), model=model.split(),
                                version=version,
                                hostname=self.hostname)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._gen_output(df)

    @command("find", help="find where an IP/MAC address is attached")
    @argument("address", type=str, description="IP/MAC address to find")
    @argument("vrf", type=str,
              description="Find within this VRF, used for IP addr")
    @argument("vlan", type=str,
              description="Find MAC within this VLAN")
    def find(self, address: str = '', vrf: str = '',
             vlan: str = ''):
        """Find the network attach point of a given IP or MAC address.
        """
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.find,
                                namespace=self.namespace,
                                hostname=self.hostname,
                                address=address.split(),
                                vlan=vlan,
                                vrf=vrf,
                                query_str=self.query_str,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._gen_output(df)
