## Supported Tables and Devices

Tables are the most basic structure we store in the suzieq database.
A table is the data that is gathered by a service, for instance BGP
is the BGP data
that the bgp service collects from routers. To see what information is collected for each table, you can use the ```<table> describe``` (```bgp describe``` for example) via suzieq-cli to get the details. To see the list of tables, you can type ```help``` in suzieq-cli or run ```suzieq-cli --help```.


|         | Cumulus Linux | Arista EOS | Linux | Cisco NXOS | Juniper JunOS<sup>1<sup> | SONIC | IOSXR | IOS | IOSXE | PanOS |
| :---------: | :---------------: | :------------: | :-------: | :------: | :-------: | :-------: | :-------: | :-------: | :-------: | :-------: |
| Arpnd   |    yes        |      yes   | yes   | yes  |  yes  | yes | yes | yes | yes | yes |
| BGP     | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| Device  | yes | yes | yes | yes | yes |  yes | yes | yes | yes |  yes |
| EvpnVni | yes | yes | no | yes<sup>2<sup> | yes | yes | no | no | no | no |
| Filesystem (fs) | yes | yes | yes | yes | no | yes | no | no | no | no |
| Interfaces | yes | yes | yes| yes | yes | yes | yes | yes | yes | yes |
| Inventory | no | yes | no | yes | yes | no | no | no | no | no |
| LLDP | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| CDP  | no | no | no | yes | no | no | no | yes | yes | no |
| Macs |yes | yes | yes | yes | yes | yes | no | yes | yes | no |
| MLAG | yes | yes | no | yes | no | no | no | no | no | no |
| Ospf |yes | yes | yes | yes | yes | yes | no | yes | yes | no |
| Routes | yes | yes | yes | yes | yes<sup>3<sup> | yes | yes | yes | yes | yes |
| sqPoller | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| VLAN | yes | yes | yes | yes | yes | yes | no | yes | yes | no |

1. Junos supported devices includes MX, QFX, QFX10K, EX, SRX, and EVO.
2. EVPN support for NXOS requires version 9.3.3 or above, please reach out if you're using older versions of NXOS
3. Junos devices are notoriously slow in responding with a large number of routes. On some older QFX5K and QFX10K, the numbers can be as low as 40K. Please use snapshot mode (--run-once=update) to get a sense of how long it takes to gather data. On MXes, we only gather connected routes for this reason. 
