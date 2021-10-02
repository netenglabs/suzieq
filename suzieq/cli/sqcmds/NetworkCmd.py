import time
import re
from types import resolve_bases
from nubia import command, argument
import pandas as pd

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
            format: str = "",
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
    def show(self, os: str = "", vendor: str = "", model: str = "",
             version: str = "") -> int:
        """
        Show network info
        """

        now = time.time()

        df = self.sqobj.get(namespace=self.namespace, os=os.split(),
                            vendor=vendor.split(), model=model.split(),
                            version=version,
                            hostname=self.hostname)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._gen_output(df)

    @command("find", help="find an address, bgp session by asn, etc")
    @argument("address", type=str, description="IP/MAC address to find")
    @argument("vrf", type=str,
              description="Find within this VRF, used for IP addr")
    @argument("vlan", type=str,
              description="Find MAC within this VLAN")
    @argument("asn", type=str, description="Autonomous system number")
    @argument("resolve_bond", type=bool, description="Resolve the bond")
    def find(self, address: str = '', asn: str = '', vrf: str = '',
             vlan: str = '', resolve_bond: bool = False):
        """Find a network object such as an IP address, BGP session, etc.
        """
        now = time.time()

        df = self.sqobj.find(
            namespace=self.namespace,
            hostname=self.hostname,
            address=address.split(),
            asn=asn.split(),
            vlan=vlan,
            vrf=vrf,
            resolve_bond=resolve_bond,
        )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._gen_output(df)
