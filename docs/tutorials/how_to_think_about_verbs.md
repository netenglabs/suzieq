# Introducing SuzieQ CLI

The SuzieQ cli is both a modal CLI (you have a shell you get into typing
`suzieq-cli` and execute all commands from there, or as a normal Linux CLI
using the classical **--** method of specifying options. Once you're inside
the modal CLI, it presents completions as you type when there are choices.
Unless explicitly mentioned, **all outputs and examples shown assume you're
using the modal CLI mode**.

To make it simple to use, all SuzieQ CLI commands follow a common structure:
`**<table> <verb> <filters>**`

This format also helps in using the REST API because that follows the same
model as well.

All verbs usually take all the filters that you can specify with one
consistent exception: `summarize` doesn't take the *columns* filter.

All commands have the common verbs: help, describe, show, summarize, top, and unique.
bgp, ospf, evpnVni and interfaces also support the `assert` verb. Finally, endpoint locator
is triggered via the ```network find```. `network` has no other verb support (the existing
use of the other verbs is deprecated and will be eliminated in release 0.21.0. Use
`namespace` instead of `network` for that functionality).

You can figure out what verbs are supported by a table by using the help verb, as in:

```bash
suzieq> bgp help
bgp: BGP protocol information

Supported verbs are: 
 - assert: Assert BGP is functioning properly
 - describe: Display the schema of the table
 - help: Show help for a command
 - show: Show address info
 - summarize: Summarize relevant information about the table
 - top: Return the top n values for a field in a table
 - unique: Get unique values (and counts) associated with requested field
suzieq> 
```

A key feature of SuzieQ is that it normalizes the data across all NOS. Thus,
in general, the poller's writes are device-specific, but the reads are
device-independent. We illustrate this by deliberately switching back and forth
across device types (usually identified by the name used with namespace.
(dual-bgp/ospf-ibgp are Cumulus-based namespaces).

## help

As the name suggests, help can be used to figure out what's possible with
each command. As show above, you can start with the basic help which shows:

```bash
suzieq> help
+-----------+-----------------------------------------------------------------+
| Command   | Description                                                     |
+-----------+-----------------------------------------------------------------+
| ?         | help                                                            |
| address   | Act on interface addresses                                      |
| arpnd     | Act on ARP/ND data                                              |
| bgp       | Act on BGP data                                                 |
| clear     | clear certain contexts for subsequent commands. Cmd is additive |
| devconfig | Act on device data                                              |
| device    | Act on device data                                              |
| evpnVni   | Act on EVPN VNI data                                            |
| fs        | Act on File System data                                         |
| help      | help                                                            |
| interface | Act on Interface data                                           |
| inventory | Act on inventory data                                           |
| lldp      | Act on LLDP data                                                |
| mac       | Act on MAC Table data                                           |
| mlag      | Act on mlag data                                                |
| namespace | Summarize namespace-wide network data                           |
| network   | Act on network-wide data                                        |
| ospf      | Act on OSPF data                                                |
| path      | build and act on path data                                      |
| route     | Act on Routes                                                   |
| set       | set certain contexts for subsequent commands. Cmd is additive   |
| sqPoller  | Act on SqPoller data                                            |
| table     | get data about data captured for various tables                 |
| topcpu    | Act on topcpu data                                              |
| topmem    | Act on topmem data                                              |
| topology  | build and act on topology data                                  |
| version   | print the suzieq version                                        |
| vlan      | Act on vlan data                                                |
+-----------+-----------------------------------------------------------------+
Built-in Commands
+----------+------------------------------------------------------------------+
| Command  | Description                                                      |
+----------+------------------------------------------------------------------+
| :verbose | Prints or changes verbosity level, accepts integer or True/False |
| connect  | Start the interactive mode                                       |
| exit     | Exits the program                                                |
| q        | Exits the program                                                |
| quit     | Exits the program                                                |
+----------+------------------------------------------------------------------+
Use help <name of command/service> [<verb>] to get more help
For example: help route or help route show
suzieq> 
```

You can look at the help for a specific command using the `<tabl> help` option. You can
find what filters are available with each verb using `<table> help command=<verb>', as in:

```bash
suzieq> bgp help command= show
bgp show: Show address info

Use quotes when providing more than one value

Arguments:
 - afiSafi: BGP AFI SAFI lens to filter the topology
 - columns: Space separated list of columns, * for all
 - end_time: End of time window, try natural language spec 
 - format: Select the pformat of the output
 - hostname: Hostname(s), space separated
 - namespace: Namespace(s), space separated
 - peer: IP address(es), in quotes, or the interface name(s), space separated
 - query_str: Trailing blank terminated pandas query format to further filter the output
 - start_time: Start of time window, try natural language spec
 - state: State of VLAN to query
 - view: View all records or just the latest
 - vrf: VRF(s), space separated
suzieq> 
```

## show

Show is the most basic verb. Every command has a show verb. It will return the
most basic data for that command. Often there is a direct mapping from a service
to a command, and the show command will show data from that table.

The show verb, like the others, allows filtering. For show, the columns filter
is especially useful.

bgp show is a good examples. It gets it's data from a single table and it shows a limited number
of the columns available.

```bash
suzieq> device show namespace=nxos
   namespace    hostname                     model      version   vendor                          architecture status       address                  bootupTimestamp
0       nxos    dcedge01                vqfx-10000    19.4R1.10  Juniper                                        alive  10.255.2.250 2021-04-21 06:52:09.329000-07:00
1       nxos      exit01  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.253        2021-04-21 06:53:03-07:00
2       nxos      exit02  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.254        2021-04-21 06:53:08-07:00
3       nxos  firewall01                        vm  18.04.3 LTS   Ubuntu                                x86-64  alive  10.255.2.249        2021-04-21 06:52:12-07:00
4       nxos      leaf01  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.189        2021-04-21 15:22:51-07:00
5       nxos      leaf02  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.188        2021-04-21 15:23:03-07:00
6       nxos      leaf03  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.190        2021-04-21 15:23:16-07:00
7       nxos      leaf04  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.191        2021-04-21 15:23:33-07:00
8       nxos   server101                        vm  18.04.3 LTS   Ubuntu                                x86-64  alive  10.255.2.204        2021-04-23 05:53:01-07:00
9       nxos   server102                        vm  18.04.3 LTS   Ubuntu                                x86-64  alive   10.255.2.39        2021-04-23 05:53:01-07:00
10      nxos   server301                        vm  18.04.3 LTS   Ubuntu                                x86-64  alive  10.255.2.140        2021-04-23 05:53:01-07:00
11      nxos   server302                        vm  18.04.3 LTS   Ubuntu                                x86-64  alive  10.255.2.114        2021-04-23 05:53:01-07:00
12      nxos     spine01  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.119        2021-04-21 06:53:10-07:00
13      nxos     spine02  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.120        2021-04-21 06:53:14-07:00
```

Path show looks some different in that you have to provide more arguments for it to work. Path
displays the path between two endpoints so it requires a src and dest.

```bash
suzieq> path show namespace=nxos src='172.16.1.101' dest='172.16.2.201'
    pathid  hopCount namespace   hostname            iif            oif       vrf   isL2  overlay  mtuMatch  inMtu  outMtu protocol         ipLookup  vtepLookup macLookup     nexthopIp hopError
0        1         0      nxos  server101          bond0          bond0   default  False    False      True   9216    9216             172.16.0.0/16                        172.16.1.254         
1        1         1      nxos     leaf01  port-channel3    Ethernet1/1  evpn-vrf   True    False      True   9216    9216      bgp  172.16.2.201/32  10.0.0.134               10.0.0.21         
2        1         2      nxos    spine01    Ethernet1/1    Ethernet1/3   default   True     True      True   9216    9216     ospf       10.0.0.134  10.0.0.134               10.0.0.13         
3        1         3      nxos     leaf03    Ethernet1/1  port-channel3  evpn-vrf  False     True      True   9216    9216      hmm  172.16.2.201/32                        172.16.2.201         
4        1         4      nxos  server301          bond0          bond0   default  False    False      True   9216    9216                                                                       
5        2         0      nxos  server101          bond0          bond0   default  False    False      True   9216    9216             172.16.0.0/16                        172.16.1.254         
6        2         1      nxos     leaf02  port-channel3    Ethernet1/1  evpn-vrf   True    False      True   9216    9216      bgp  172.16.2.201/32  10.0.0.134               10.0.0.21         
7        2         2      nxos    spine01    Ethernet1/2    Ethernet1/3   default   True     True      True   9216    9216     ospf       10.0.0.134  10.0.0.134               10.0.0.13         
8        2         3      nxos     leaf03    Ethernet1/1  port-channel3  evpn-vrf  False     True      True   9216    9216      hmm  172.16.2.201/32                        172.16.2.201         
9        2         4      nxos  server301          bond0          bond0   default  False    False      True   9216    9216                                                                       
10       3         0      nxos  server101          bond0          bond0   default  False    False      True   9216    9216             172.16.0.0/16                        172.16.1.254         
11       3         1      nxos     leaf01  port-channel3    Ethernet1/2  evpn-vrf   True    False      True   9216    9216      bgp  172.16.2.201/32  10.0.0.134               10.0.0.22         
12       3         2      nxos    spine02    Ethernet1/1    Ethernet1/3   default   True     True      True   9216    9216     ospf       10.0.0.134  10.0.0.134               10.0.0.13         
13       3         3      nxos     leaf03    Ethernet1/2  port-channel3  evpn-vrf  False     True      True   9216    9216      hmm  172.16.2.201/32                        172.16.2.201         
14       3         4      nxos  server301          bond0          bond0   default  False    False      True   9216    9216                                                                       
15       4         0      nxos  server101          bond0          bond0   default  False    False      True   9216    9216             172.16.0.0/16                        172.16.1.254         
16       4         1      nxos     leaf02  port-channel3    Ethernet1/2  evpn-vrf   True    False      True   9216    9216      bgp  172.16.2.201/32  10.0.0.134               10.0.0.22         
17       4         2      nxos    spine02    Ethernet1/2    Ethernet1/3   default   True     True      True   9216    9216     ospf       10.0.0.134  10.0.0.134               10.0.0.13         
18       4         3      nxos     leaf03    Ethernet1/2  port-channel3  evpn-vrf  False     True      True   9216    9216      hmm  172.16.2.201/32                        172.16.2.201         
19       4         4      nxos  server301          bond0          bond0   default  False    False      True   9216    9216                                                                       
20       5         0      nxos  server101          bond0          bond0   default  False    False      True   9216    9216             172.16.0.0/16                        172.16.1.254         
21       5         1      nxos     leaf01  port-channel3    Ethernet1/1  evpn-vrf   True    False      True   9216    9216      bgp  172.16.2.201/32  10.0.0.134               10.0.0.21         
22       5         2      nxos    spine01    Ethernet1/1    Ethernet1/4   default   True     True      True   9216    9216     ospf       10.0.0.134  10.0.0.134               10.0.0.14         
23       5         3      nxos     leaf04    Ethernet1/1  port-channel3  evpn-vrf  False     True      True   9216    9216      hmm  172.16.2.201/32                        172.16.2.201         
24       5         4      nxos  server301          bond0          bond0   default  False    False      True   9216    9216                                                                       
25       6         0      nxos  server101          bond0          bond0   default  False    False      True   9216    9216             172.16.0.0/16                        172.16.1.254         
26       6         1      nxos     leaf02  port-channel3    Ethernet1/1  evpn-vrf   True    False      True   9216    9216      bgp  172.16.2.201/32  10.0.0.134               10.0.0.21         
27       6         2      nxos    spine01    Ethernet1/2    Ethernet1/4   default   True     True      True   9216    9216     ospf       10.0.0.134  10.0.0.134               10.0.0.14         
28       6         3      nxos     leaf04    Ethernet1/1  port-channel3  evpn-vrf  False     True      True   9216    9216      hmm  172.16.2.201/32                        172.16.2.201         
29       6         4      nxos  server301          bond0          bond0   default  False    False      True   9216    9216                                                                       
30       7         0      nxos  server101          bond0          bond0   default  False    False      True   9216    9216             172.16.0.0/16                        172.16.1.254         
31       7         1      nxos     leaf01  port-channel3    Ethernet1/2  evpn-vrf   True    False      True   9216    9216      bgp  172.16.2.201/32  10.0.0.134               10.0.0.22         
32       7         2      nxos    spine02    Ethernet1/1    Ethernet1/4   default   True     True      True   9216    9216     ospf       10.0.0.134  10.0.0.134               10.0.0.14         
33       7         3      nxos     leaf04    Ethernet1/2  port-channel3  evpn-vrf  False     True      True   9216    9216      hmm  172.16.2.201/32                        172.16.2.201         
34       7         4      nxos  server301          bond0          bond0   default  False    False      True   9216    9216                                                                       
35       8         0      nxos  server101          bond0          bond0   default  False    False      True   9216    9216             172.16.0.0/16                        172.16.1.254         
36       8         1      nxos     leaf02  port-channel3    Ethernet1/2  evpn-vrf   True    False      True   9216    9216      bgp  172.16.2.201/32  10.0.0.134               10.0.0.22         
37       8         2      nxos    spine02    Ethernet1/2    Ethernet1/4   default   True     True      True   9216    9216     ospf       10.0.0.134  10.0.0.134               10.0.0.14         
38       8         3      nxos     leaf04    Ethernet1/2  port-channel3  evpn-vrf  False     True      True   9216    9216      hmm  172.16.2.201/32                        172.16.2.201         
39       8         4      nxos  server301          bond0          bond0   default  False    False      True   9216    9216                                                                       
suzieq> 
```

```
table show
```

Table show looks a bit different than the other commands, because table show is showing
the tables in the database, not directly looking at data inside tables.

```bash
suzieq> table show namespace=eos
         table                        firstTime                         lastTime  intervals  allRows  namespaceCnt  deviceCnt
0        arpnd 2021-06-06 17:19:36.216000-07:00 2021-06-06 17:19:41.909000-07:00         12       82             1         14
1          bgp 2021-06-06 17:19:35.569000-07:00 2021-06-06 17:19:37.989000-07:00         10       96             1         10
2    devconfig 2021-06-06 17:19:34.534000-07:00 2021-06-06 17:19:36.891000-07:00          9        9             1          9
3       device 2021-06-06 17:19:35.797000-07:00 2021-06-06 17:19:40.016000-07:00         12       14             1         14
4      evpnVni 2021-06-06 17:19:37.153000-07:00 2021-06-06 17:19:37.461000-07:00          6       14             1          6
5           fs 2021-06-06 17:19:36.216000-07:00 2021-06-06 17:19:42.495000-07:00          6       66             1          6
6   ifCounters 2021-06-06 17:19:35.797000-07:00 2021-06-06 17:19:37.450000-07:00         11       38             1         13
7   interfaces 2021-06-06 17:19:35.379000-07:00 2021-06-06 17:19:39.345000-07:00         11      202             1         14
8         lldp 2021-06-06 17:19:36.213000-07:00 2021-06-06 17:19:39.139000-07:00          8       36             1          9
9         macs 2021-06-06 17:19:34.997000-07:00 2021-06-06 17:19:36.019000-07:00          9      192             1         11
10        mlag 2021-06-06 17:19:37.425000-07:00 2021-06-06 17:19:37.894000-07:00          4        4             1          4
11      ospfIf 2021-06-06 17:19:37.058000-07:00 2021-06-06 17:19:37.660000-07:00          8       36             1          8
12     ospfNbr 2021-06-06 17:19:37.451000-07:00 2021-06-06 17:19:37.907000-07:00          8       24             1          8
13      routes 2021-06-06 17:19:34.530000-07:00 2021-06-06 17:19:36.627000-07:00         13      276             1         14
14    sqPoller 2022-05-14 21:04:59.189000-07:00 2022-05-14 21:05:01.207000-07:00        197      197             1         14
15        time 2021-06-06 17:19:34.533000-07:00 2021-06-06 17:19:35.208000-07:00         11       13             1         13
16      topcpu 2021-06-06 17:19:35.800000-07:00 2021-06-06 17:19:36.214000-07:00          2       35             1          5
17      topmem 2021-06-06 17:19:35.374000-07:00 2021-06-06 17:19:35.585000-07:00          5       48             1          5
18        vlan 2021-06-06 17:19:34.532000-07:00 2021-06-06 17:19:36.433000-07:00          9       27             1          9
19       TOTAL 2021-06-06 17:19:34.530000-07:00 2022-05-14 21:05:01.207000-07:00        197     1409             1         14
suzieq> 
```

Some of the tables have a lot of columns. We have a standard set of default columns for
each table. However, you can add a columns= filter to add more columns or see less. columns=*
shows all the columns. This example shows the BGP table using specific the columns= filter (the output is snipped for brevity).

```bash
suzieq> bgp show namespace=ospf-ibgp columns='hostname vrf peer peerHostname state asn bfdStatus updateSource'
    hostname           vrf    peer peerHostname        state    asn bfdStatus             updateSource
0     edge01       default  eth1.2       exit01  Established  65530  disabled            169.254.254.2
1     edge01       default  eth1.3       exit01  Established  65530  disabled            169.254.254.6
2     edge01       default  eth1.4       exit01  Established  65530  disabled           169.254.254.10
3     edge01       default  eth2.2       exit02  Established  65530  disabled            169.254.253.2
4     edge01       default  eth2.3       exit02  Established  65530  disabled            169.254.253.6
5     edge01       default  eth2.4       exit02  Established  65530  disabled           169.254.253.10
6     exit01       default    swp1      spine01  Established  65000        up  fe80::5054:ff:feff:73be
7     exit01       default    swp1      spine01  Established  65000        up  fe80::5054:ff:feff:73be
8     exit01       default    swp2      spine02  Established  65000        up  fe80::5054:ff:fe28:db32
9     exit01       default    swp2      spine02  Established  65000        up  fe80::5054:ff:fe28:db32
10    exit01       default  swp5.2       edge01  Established  65000  disabled            169.254.254.1
11    exit01      evpn-vrf  swp5.3       edge01  Established  65000  disabled            169.254.254.5
12    exit01  internet-vrf  swp5.4       edge01  Established  65001      down            169.254.254.9
13    exit01  internet-vrf    swp6     internet  Established  65001        up            169.254.127.1
14    exit02       default    swp1      spine01  Established  65000        up  fe80::5054:ff:fe93:9e21
...
34   spine01       default    swp4       leaf04  Established  65000        up  fe80::5054:ff:fe7a:b002
35   spine01       default    swp5       exit02  Established  65000        up  fe80::5054:ff:fecf:3b50
36   spine01       default    swp5       exit02  Established  65000        up  fe80::5054:ff:fecf:3b50
37   spine01       default    swp6       exit01  Established  65000        up  fe80::5054:ff:fe83:94bc
38   spine01       default    swp6       exit01  Established  65000        up  fe80::5054:ff:fe83:94bc
39   spine02       default    swp1       leaf01  Established  65000        up  fe80::5054:ff:fe54:3d39
40   spine02       default    swp2       leaf02  Established  65000        up    fe80::5054:ff:fed1:da
41   spine02       default    swp3       leaf03  Established  65000        up  fe80::5054:ff:fe25:b05b
42   spine02       default    swp4       leaf04  Established  65000        up  fe80::5054:ff:fea7:ba2d
43   spine02       default    swp6       exit01  Established  65000        up  fe80::5054:ff:fe5d:daac
44   spine02       default    swp6       exit01  Established  65000        up  fe80::5054:ff:fe5d:daac
```

Some commands have specific filters.
If you want to look at specific interface types, such as virtual interfaces

```bash
suzieq> interface show namespace=junos hostname=leaf01 type='vxlan vrf vlan'
  namespace hostname    ifname state adminState  type   mtu  vlan    master      ipAddressList ip6AddressList
0     junos   leaf01  evpn-vrf    up         up   vrf  1500     0                           []             []
1     junos   leaf01    irb.10    up         up  vlan  1500    10  evpn-vrf  [172.16.1.254/24]             []
2     junos   leaf01    irb.30    up         up  vlan  1500    30  evpn-vrf  [172.16.3.254/24]             []
suzieq> 
```

if you want to investigate why bgp sessions are failing

```bash
suzieq> bgp show columns='namespace hostname vrf peer state reason notificnReason' state= NotEstd
   namespace hostname      vrf  peer    state                     reason notificnReason
0  ospf-ibgp   exit02  default  swp2  NotEstd  Waiting for Peer IPv6 LLA               
suzieq> 
```

## summarize

Summarize works through the data in the table and produces a summary of what Suzieq
thinks are the most important information.

```bash
suzieq> interface summarize namespace=eos
                               eos
deviceCnt                       14
interfaceCnt                   186
devicesWithL2Cnt                 6
devicesWithVxlanCnt              6
ifDownCnt                        1
ifAdminDownCnt                   0
ifWithMultipleIPCnt              8
uniqueMTUCnt                     8
uniqueIfTypesCnt                13
speedCnt                         5
ifChangesStat          [0, 0, 0.0]
ifPerDeviceStat      [5, 42, 11.5]
uniqueIPv4AddrCnt               55
uniqueIPv6AddrCnt                0
suzieq> 
```

In any of our summaries, statistics that end with Cnt, such as vendorCnt,
if there are three or less of them, then we break out the items and provide
their count. In this example, there are 2 vendorCnts, which are Cumulus
and Ubuntu. Statistics that end with Stat, such as upTimesStat, shows
lists of three items bracketed in [] show [min, max, median] of the values
to give you an overview of the distribution. For any of these values, you
can use the ‘unique’ verb to dive into the column and see the whole list.

```bash
suzieq> ospf summarize namespace=eos
                                                                            eos
deviceCnt                                                                     8
peerCnt                                                                      36
stubbyPeerCnt                                                                 0
passivePeerCnt                                                               12
unnumberedPeerCnt                                                            32
failedPeerCnt                                                                 0
area                                                            {'0.0.0.0': 36}
vrf                                                             {'default': 36}
helloTime                                                            {10.0: 36}
deadTime                                                             {40.0: 36}
retxTime                                                              {5.0: 36}
networkType                                        {'p2p': 24, 'broadcast': 12}
adjChangesStat                                                  [0.0, 7.0, 6.0]
upTimeStat         [1 days 05:37:54, 27 days 04:16:05, 27 days 04:14:50.500000]
suzieq> 
```

```bash
suzieq> path summarize src='172.16.1.101' dest='172.16.4.104' namespace=dual-bgp
                      dual-bgp
totalPaths                   8
perHopEcmp     [2, 3, 4, 3, 1]
maxPathLength                5
avgPathLength              4.5
uniqueDevices                8
pathMtu                   1500
usesOverlay              False
mtuMismatch               True
suzieq> 
```

## unique

Unique takes a single column and produces the list of unique items and the count of
how many times that item occurs. ```unique``` is very useful for diving in to understand
the details of your network.

For example, after examining the output of ```interface summarize```, we want
to dig deeper to figure out why there are 8 different MTUs (`uniqueMtuCnt` is 8 in the
output above). We can use unique as follows:

```bash
suzieq> interface unique columns=mtu namespace=eos
     mtu
0     -1
1   1500
2   1514
3   9164
4   9214
5   9216
6  65535
7  65536
suzieq> 
```

We can get a count of the number of interfaces with those MTUs as well:

```bash
suzieq> interface unique columns=mtu namespace=eos count=True
     mtu  numRows
0     -1        6
1   9216       12
2  65535       12
3  65536       13
4   9164       14
5   1514       18
6   9214       28
7   1500       83
suzieq> 
```

We can then delve even deeper to identify what interfaces have an MTU of 65535, for example:

```bash
suzieq> interface show namespace=eos mtu=65535
   namespace hostname     ifname state adminState      type    mtu  vlan master    ipAddressList ip6AddressList
0        eos   exit01  Loopback0    up         up  loopback  65535     0          [10.0.0.31/32]             []
1        eos   exit02  Loopback0    up         up  loopback  65535     0          [10.0.0.32/32]             []
2        eos   leaf01  Loopback0    up         up  loopback  65535     0          [10.0.0.11/32]             []
3        eos   leaf01  Loopback1    up         up  loopback  65535     0         [10.0.0.112/32]             []
4        eos   leaf02  Loopback0    up         up  loopback  65535     0          [10.0.0.12/32]             []
5        eos   leaf02  Loopback1    up         up  loopback  65535     0         [10.0.0.112/32]             []
6        eos   leaf03  Loopback0    up         up  loopback  65535     0          [10.0.0.13/32]             []
7        eos   leaf03  Loopback1    up         up  loopback  65535     0         [10.0.0.134/32]             []
8        eos   leaf04  Loopback0    up         up  loopback  65535     0          [10.0.0.14/32]             []
9        eos   leaf04  Loopback1    up         up  loopback  65535     0         [10.0.0.134/32]             []
10       eos  spine01  Loopback0    up         up  loopback  65535     0          [10.0.0.21/32]             []
11       eos  spine02  Loopback0    up         up  loopback  65535     0          [10.0.0.22/32]             []
suzieq> 
```

You can even look at both 65535 and 65536 by either specifying both values in
the command

```bash
suzieq> interface show namespace=eos mtu='65535 65536'
   namespace    hostname     ifname state adminState                       type    mtu  vlan master    ipAddressList                  ip6AddressList
0        eos    dcedge01        dsc    up         up                       null  65536     0                      []                              []
1        eos    dcedge01        esi    up         up                       vtep  65536     0                      []                              []
2        eos    dcedge01       fti0    up         up  flexible-tunnel-interface  65536     0                      []                              []
3        eos    dcedge01   gr-0/0/0    up         up                        gre  65536     0                      []                              []
4        eos    dcedge01        lo0    up         up                   loopback  65536     0                      []                              []
5        eos    dcedge01      lo0.0    up         up               subinterface  65536     0          [10.0.0.41/32]  [fe80::205:860f:fc71:f000/128]
6        eos    dcedge01  lo0.16385    up         up               subinterface  65536     0                      []                              []
7        eos    dcedge01       vtep    up         up                       vtep  65536     0                      []                              []
8        eos      exit01  Loopback0    up         up                   loopback  65535     0          [10.0.0.31/32]                              []
9        eos      exit02  Loopback0    up         up                   loopback  65535     0          [10.0.0.32/32]                              []
10       eos  firewall01         lo    up         up                   loopback  65536     0         [10.0.0.200/32]                              []
11       eos      leaf01  Loopback0    up         up                   loopback  65535     0          [10.0.0.11/32]                              []
12       eos      leaf01  Loopback1    up         up                   loopback  65535     0         [10.0.0.112/32]                              []
13       eos      leaf02  Loopback0    up         up                   loopback  65535     0          [10.0.0.12/32]                              []
14       eos      leaf02  Loopback1    up         up                   loopback  65535     0         [10.0.0.112/32]                              []
15       eos      leaf03  Loopback0    up         up                   loopback  65535     0          [10.0.0.13/32]                              []
16       eos      leaf03  Loopback1    up         up                   loopback  65535     0         [10.0.0.134/32]                              []
17       eos      leaf04  Loopback0    up         up                   loopback  65535     0          [10.0.0.14/32]                              []
18       eos      leaf04  Loopback1    up         up                   loopback  65535     0         [10.0.0.134/32]                              []
19       eos   server101         lo    up         up                   loopback  65536     0                      []                              []
20       eos   server102         lo    up         up                   loopback  65536     0                      []                              []
21       eos   server301         lo    up         up                   loopback  65536     0                      []                              []
22       eos   server302         lo    up         up                   loopback  65536     0                      []                              []
23       eos     spine01  Loopback0    up         up                   loopback  65535     0          [10.0.0.21/32]                              []
24       eos     spine02  Loopback0    up         up                   loopback  65535     0          [10.0.0.22/32]                              []
suzieq> 
```

Or by using an operator as in:

```bash
suzieq> interface show namespace=eos mtu='> 10000'
   namespace    hostname     ifname state adminState                       type    mtu  vlan master    ipAddressList                  ip6AddressList
0        eos    dcedge01        dsc    up         up                       null  65536     0                      []                              []
1        eos    dcedge01        esi    up         up                       vtep  65536     0                      []                              []
2        eos    dcedge01       fti0    up         up  flexible-tunnel-interface  65536     0                      []                              []
3        eos    dcedge01   gr-0/0/0    up         up                        gre  65536     0                      []                              []
4        eos    dcedge01        lo0    up         up                   loopback  65536     0                      []                              []
5        eos    dcedge01      lo0.0    up         up               subinterface  65536     0          [10.0.0.41/32]  [fe80::205:860f:fc71:f000/128]
6        eos    dcedge01  lo0.16385    up         up               subinterface  65536     0                      []                              []
7        eos    dcedge01       vtep    up         up                       vtep  65536     0                      []                              []
8        eos      exit01  Loopback0    up         up                   loopback  65535     0          [10.0.0.31/32]                              []
9        eos      exit02  Loopback0    up         up                   loopback  65535     0          [10.0.0.32/32]                              []
10       eos  firewall01         lo    up         up                   loopback  65536     0         [10.0.0.200/32]                              []
11       eos      leaf01  Loopback0    up         up                   loopback  65535     0          [10.0.0.11/32]                              []
12       eos      leaf01  Loopback1    up         up                   loopback  65535     0         [10.0.0.112/32]                              []
13       eos      leaf02  Loopback0    up         up                   loopback  65535     0          [10.0.0.12/32]                              []
14       eos      leaf02  Loopback1    up         up                   loopback  65535     0         [10.0.0.112/32]                              []
15       eos      leaf03  Loopback0    up         up                   loopback  65535     0          [10.0.0.13/32]                              []
16       eos      leaf03  Loopback1    up         up                   loopback  65535     0         [10.0.0.134/32]                              []
17       eos      leaf04  Loopback0    up         up                   loopback  65535     0          [10.0.0.14/32]                              []
18       eos      leaf04  Loopback1    up         up                   loopback  65535     0         [10.0.0.134/32]                              []
19       eos   server101         lo    up         up                   loopback  65536     0                      []                              []
20       eos   server102         lo    up         up                   loopback  65536     0                      []                              []
21       eos   server301         lo    up         up                   loopback  65536     0                      []                              []
22       eos   server302         lo    up         up                   loopback  65536     0                      []                              []
23       eos     spine01  Loopback0    up         up                   loopback  65535     0          [10.0.0.21/32]                              []
24       eos     spine02  Loopback0    up         up                   loopback  65535     0          [10.0.0.22/32]                              []
suzieq> 
```

Usually, specifying multiple values means you want columns that match any of those values. But
Specifying both < and > operators acts as the equivalent of in between those values (output is
snipped for brevity):

```bash
suzieq> interface show namespace=eos mtu='> 1500 < 10000'
   namespace   hostname         ifname state adminState        type   mtu  vlan         master                 ipAddressList ip6AddressList
0        eos   dcedge01            em0    up         up    ethernet  1514     0                                           []             []
1        eos   dcedge01            em1    up         up    ethernet  1514     0                                           []             []
2        eos   dcedge01            em2    up         up    ethernet  1514     0                                           []             []
3        eos   dcedge01            em3    up         up    ethernet  1514     0                                           []             []
4        eos   dcedge01            em4    up         up    ethernet  1514     0                                           []             []
5        eos   dcedge01            vme  down         up   mgmt-vlan  1514     0                                           []             []
6        eos   dcedge01       xe-0/0/0    up         up    ethernet  1514     0                                           []             []
7        eos   dcedge01       xe-0/0/1    up         up    ethernet  1514     0                                           []             []
8        eos   dcedge01       xe-0/0/2    up         up    ethernet  1514     0                                           []             []
9        eos   dcedge01       xe-0/0/3    up         up    ethernet  1514     0                                           []             []
10       eos   dcedge01       xe-0/0/4    up         up    ethernet  1514     0                                           []             []
11       eos   dcedge01       xe-0/0/5    up         up    ethernet  1514     0                                           []             []
12       eos   dcedge01       xe-0/0/6    up         up    ethernet  1514     0                                           []             []
13       eos   dcedge01       xe-0/0/7    up         up    ethernet  1514     0                                           []             []
14       eos   dcedge01       xe-0/0/8    up         up    ethernet  1514     0                                           []             []
15       eos   dcedge01       xe-0/0/9    up         up    ethernet  1514     0                                           []             []
16       eos   dcedge01      xe-0/0/10    up         up    ethernet  1514     0                                           []             []
...
69       eos  server302          bond0    up         up        bond  9216     0                            [172.16.3.202/24]             []
70       eos  server302           eth1    up         up  bond_slave  9216     0          bond0                            []             []
71       eos  server302           eth2    up         up  bond_slave  9216     0          bond0                            []             []
```

## find

The command `network find` is used to locate where a specified MAC or IP address is located in the network i.e. the first hop switch it is attached to.

```bash
suzieq> network find namespace=nxos address='172.16.1.101'
  namespace hostname       vrf     ipAddress  vlan            macaddr         ifname  bondMembers     type  l2miss
0      nxos   leaf01  evpn-vrf  172.16.1.101    10  32:bb:c5:b5:3a:20  port-channel3  Ethernet1/3  bridged   False
1      nxos   leaf02  evpn-vrf  172.16.1.101    10  32:bb:c5:b5:3a:20  port-channel3  Ethernet1/3  bridged   False
suzieq> 
```

This works across multiple scenarios from dual-attached MLAG hosts in a distributed EVPN network to a access-aggregation campus network.

## assert

assert works on bgp, evpnVni, interface, and ospf. asserts
run checks that are true for a network to be running correctly. For each
service that has an assert you get an output that shows all the data
necessary for the checks, a pass/fail column and a reason column for any
failed checks.

Here's an example of BGP assert (output snipped for brevity).

```bash
suzieq> bgp assert namespace=eos 
   namespace    hostname           vrf            peer    asn  peerAsn        state peerHostname result               assertReason
0        eos    dcedge01       default   169.254.127.1  65534    65522  Established       exit01   fail  Not all Afi/Safis enabled
1        eos    dcedge01       default   169.254.127.3  65534    65522  Established       exit02   fail  Not all Afi/Safis enabled
2        eos      exit01       default       10.0.0.21  64520    64520  Established      spine01   pass                          -
3        eos      exit01       default       10.0.0.22  64520    64520  Established      spine02   pass                          -
4        eos      exit01       default   169.254.254.2  65520    65533  Established   firewall01   pass                          -
5        eos      exit01      evpn-vrf   169.254.254.6  65521    65533  Established   firewall01   pass                          -
6        eos      exit01  internet-vrf   169.254.127.0  65522    65534  Established     dcedge01   pass                          -
7        eos      exit01  internet-vrf  169.254.254.10  65522    65533  Established   firewall01   pass                          -
8        eos      exit02       default       10.0.0.21  64520    64520  Established      spine01   pass                          -
...
37       eos     spine02       default       10.0.0.14  64520    64520  Established       leaf04   pass                          -
38       eos     spine02       default       10.0.0.31  64520    64520  Established       exit01   pass                          -
39       eos     spine02       default       10.0.0.32  64520    64520  Established       exit02   pass                          -
Assert failed
suzieq> 
```

When an assert fails, it returns -1. You can use this in the Linux mode to then
trap cases where the assert failure can be used inside an Ansible playbook, for
example.

```bash
~/work/suzieq$ suzieq-cli bgp assert --namespace=eos
   namespace    hostname           vrf            peer    asn  peerAsn        state peerHostname result               assertReason
0        eos    dcedge01       default   169.254.127.1  65534    65522  Established       exit01   fail  Not all Afi/Safis enabled
1        eos    dcedge01       default   169.254.127.3  65534    65522  Established       exit02   fail  Not all Afi/Safis enabled
2        eos      exit01       default       10.0.0.21  64520    64520  Established      spine01   pass                          -
3        eos      exit01       default       10.0.0.22  64520    64520  Established      spine02   pass                          -
4        eos      exit01       default   169.254.254.2  65520    65533  Established   firewall01   pass                          -
5        eos      exit01      evpn-vrf   169.254.254.6  65521    65533  Established   firewall01   pass                          -
6        eos      exit01  internet-vrf   169.254.127.0  65522    65534  Established     dcedge01   pass                          -
7        eos      exit01  internet-vrf  169.254.254.10  65522    65533  Established   firewall01   pass                          -
8        eos      exit02       default       10.0.0.21  64520    64520  Established      spine01   pass                          -
...
37       eos     spine02       default       10.0.0.14  64520    64520  Established       leaf04   pass                          -
38       eos     spine02       default       10.0.0.31  64520    64520  Established       exit01   pass                          -
39       eos     spine02       default       10.0.0.32  64520    64520  Established       exit02   pass                          -
Assert failed
~/work/suzieq$ echo $?
255
~/work/suzieq$
```

You can filter out the result to only show those rows that failed like this:

```bash
suzieq> bgp assert namespace=eos result= fail
  namespace  hostname      vrf           peer    asn  peerAsn        state peerHostname result               assertReason
0       eos  dcedge01  default  169.254.127.1  65534    65522  Established       exit01   fail  Not all Afi/Safis enabled
1       eos  dcedge01  default  169.254.127.3  65534    65522  Established       exit02   fail  Not all Afi/Safis enabled
Assert failed
suzieq> 
```

## top

top shows the rows with the maximum value for the column specified. For example, to see the interfaces with the most flaps, use:

```bash
suzieq> interface top what=numChanges namespace=nxos
  namespace hostname         ifname state adminState        type   mtu  vlan         master ipAddressList ip6AddressList  numChanges                        timestamp
0      nxos   leaf03    Ethernet1/6    up         up  bond_slave  9216     1  port-channel1            []             []           6 2021-04-24 07:40:58.539000-07:00
1      nxos   leaf04    Ethernet1/6    up         up  bond_slave  9216     1  port-channel1            []             []           5 2021-04-24 07:40:59.180000-07:00
2      nxos   leaf04    Ethernet1/3    up         up  bond_slave  9216    20  port-channel3            []             []           5 2021-04-24 07:40:59.180000-07:00
3      nxos   leaf03    Ethernet1/5    up         up  bond_slave  9216     1  port-channel1            []             []           5 2021-04-24 07:40:58.539000-07:00
4      nxos   leaf04  port-channel3    up         up        bond  9216    20         bridge            []             []           4 2021-04-24 07:40:59.180000-07:00
suzieq> 
```

To see the device with the maximum uptime:

```bash
suzieq> device top what=uptime namespace=nxos
  namespace    hostname                     model      version   vendor                          architecture status       address                  bootupTimestamp                 uptime                        timestamp
0      nxos    dcedge01                vqfx-10000    19.4R1.10  Juniper                                        alive  10.255.2.250 2021-04-21 06:52:09.329000-07:00        3 days 00:48:49 2021-04-24 07:40:58.329000-07:00
1      nxos  firewall01                        vm  18.04.3 LTS   Ubuntu                                x86-64  alive  10.255.2.249        2021-04-21 06:52:12-07:00 3 days 00:48:44.497000 2021-04-24 07:40:56.497000-07:00
2      nxos      exit01  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.253        2021-04-21 06:53:03-07:00 3 days 00:48:02.064000 2021-04-24 07:41:05.064000-07:00
3      nxos      exit02  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.254        2021-04-21 06:53:08-07:00 3 days 00:47:57.196000 2021-04-24 07:41:05.196000-07:00
4      nxos     spine01  Nexus9000 C9300v Chassis       9.3(4)    Cisco  Intel Core Processor (Skylake, IBRS)  alive  10.255.2.119        2021-04-21 06:53:10-07:00 3 days 00:47:53.589000 2021-04-24 07:41:03.589000-07:00
suzieq> 
```

Top can only be used with columns that are numeric.

## lpm

lpm only works on the route command, and is used to display which forwarding table entries
would be hit for a given address:

```bash
suzieq> route lpm namespace=junos address='10.0.0.112'
   namespace    hostname           vrf     prefix       nexthopIps          oifs         protocol source  preference  ipvers   action
0      junos    dcedge01       default  0.0.0.0/0     [10.255.5.1]       [em0.0]  access-internal                 12       4  forward
1      junos      exit01       default  0.0.0.0/0     [10.255.5.1]       [em0.0]  access-internal                 12       4  forward
2      junos      exit01  internet-vrf  0.0.0.0/0  [169.254.127.0]  [xe-0/0/3.0]              bgp                170       4  forward
3      junos      exit02       default  0.0.0.0/0     [10.255.5.1]       [em0.0]  access-internal                 12       4  forward
4      junos      exit02  internet-vrf  0.0.0.0/0  [169.254.127.2]  [xe-0/0/3.0]              bgp                170       4  forward
5      junos  firewall01       default  0.0.0.0/0     [10.255.5.1]        [eth0]                                  20       4  forward
6      junos      leaf01       default  0.0.0.0/0     [10.255.5.1]       [em0.0]  access-internal                 12       4  forward
7      junos      leaf02       default  0.0.0.0/0     [10.255.5.1]       [em0.0]  access-internal                 12       4  forward
8      junos   server101       default  0.0.0.0/0     [10.255.5.1]        [eth0]                                  20       4  forward
9      junos   server102       default  0.0.0.0/0     [10.255.5.1]        [eth0]                                  20       4  forward
10     junos   server201       default  0.0.0.0/0     [10.255.5.1]        [eth0]                                  20       4  forward
11     junos   server202       default  0.0.0.0/0     [10.255.5.1]        [eth0]                                  20       4  forward
12     junos     spine01       default  0.0.0.0/0     [10.255.5.1]       [em0.0]  access-internal                 12       4  forward
13     junos     spine02       default  0.0.0.0/0     [10.255.5.1]       [em0.0]  access-internal                 12       4  forward
suzieq> 
```

## describe

describe is used to describe the schema of the table i.e. the data gathered for the table.

```
suzieq> route describe
                     name                                               type key display                                        description
0                  action                                             string          10  Action taken on this route: forward, blackhole...
1                  active                                            boolean                             If this entry is active or deleted
2              asPathList  {'type': 'array', 'items': {'name': 'asPath', ...                            List of AS paths, platform-specific
3           deviceSession                                          timestamp                                         Device boot session id
4      hardwareProgrammed                                             string              Hardware programmed state of route, platform-s...
5                hostname                                             string   1       1               Hostname associated with this record
6                  ipvers                                               long           9                                IP version of route
7                  metric                                               long                Metric associated with route, platform-specific
8               namespace                                             string   0       0              Namespace associated with this record
9              nexthopIps  {'type': 'array', 'items': {'name': 'nexthopIp...           4                                List of nexthop IPs
10            numNexthops                                               long                                             Number of nexthops
11                   oifs  {'type': 'array', 'items': {'name': 'oif', 'ty...           5                        List of outgoing interfaces
12             preference                                               long           8  Preference associated with route, platform-spe...
13                 prefix                                             string   3       3                                    IP route prefix
14              prefixlen                                               long                                         IP route prefix length
15               protocol                                             string           6               Protocol that created for this route
16               routeTag                                             string              Tags associated with this route, platform-spec...
17                 source                                             string           7  Source IP address used if this route is picked...
18                 sqvers                                             string                                 Schema version, not selectable
19  statusChangeTimestamp                                          timestamp                               The last time this route changed
20              timestamp                                          timestamp          11                                                   
21             validState                                             string                        Valid state of route, platform-specific
22                    vrf                                             string   2       2                     VRF associated with this route
23                weights  {'type': 'array', 'items': {'name': 'weight', ...                        List of weights associated with nexthop
suzieq> 
```

## Configuring CLI itself

There are some additional commands triggered via the `set` and `clear` commands to configure certain contexts and the output of the CLI.

* `set pager=on`: is used to enable a rudimentary pager to paginate the output. The default is no pagination.
* `set col-width=<number>`: is used to enable a maximum width of a column in the display. Setting it to 120 or 150 can enable the visibility of the entire column in cases such as with the `summarize` verb.
* `set max-rows=<number>`: is used to control how many rows you can see at any given time. By default, everything is shown if there are no more tha n 256 total rows. Beyond that, you see the first few lines of the start, the ellipsis (...), followed by the last few rows. Set to 0 to always show all. **Warning**: setting it to 0 means it can take a very long time to display if there's a large dataset. Its recommended to use filters to tame the output to a manageable size.
* `set all-columns=yes`: is used to enable the display of all columns, wrapping around if necessary.
* `set namespace=<namespace>`: is used to enable the context for all commands henceforth. This means you don't need to type the filter `namespace=` with every command. You can still that filter to override the namespace for certain commands.
* `set hosname=<hostname>`: Same as namespace, but for a hostname.

## Debugging CLI Exceptions

The CLI in general catches exceptions and displays them in a nice format. For example:

```bash
suzieq> bgp show query-str='foobar=="user"'
                                                 error
0  ERROR: UserQueryError: name 'foobar' is not defined
suzieq>

When reporting such errors, its useful for the developer to know where the error occurred. Use the CLI option `set debug=True` to display the traceback which you can then use to report the issue.
