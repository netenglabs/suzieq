from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.topology import TopologyObj


@command("topology", help="build and act on topology data")
@argument("polled", description="Is the device polled by Suzieq",
          choices=['True', 'False'])
@argument("ifname", description="Interface name(s), space separated")
@argument("via",
          description="Protocol(s) via which nodes are connected, "
          "space separated")
@argument("vrf", description="VRF(s), space separated")
@argument("asn", description="BGP ASN(s), space separated")
@argument("area", description="OSPF Area(s), space separated")
@argument("afiSafi", description="BGP AFI SAFI lens to filter the topology")
@ argument("peerHostname",
           description="Peer hostname(s), space separated, "
           "space separated")
class TopologyCmd(SqTableCommand):
    """Information about the topology constructed from various protocols"""

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
            polled: str = '',
            ifname: str = '',
            via: str = '',
            vrf: str = '',
            asn: str = '',
            area: str = '',
            peerHostname: str = '',
            afiSafi: str = ''
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
        self.lvars = {
            'polled': str(polled),
            'ifname': ifname.split(),
            'asn': asn.split(),
            'area': area.split(),
            'via': via.split(),
            'vrf': vrf.split(),
            'peerHostname': peerHostname.split(),
            'afiSafi': afiSafi,
        }
