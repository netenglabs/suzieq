# Release Notes

## 0.15.6 (Nov 14, 2021)

Another bugfix release of the 0.15 release train, hopefully the last. Here's what's fixed/new in this release:

* Help strings associated with every field in every table's schema. Look at bgp describe for example
* Fix regex support for namespace and hostname
* LLDP: Add support for filtering by peer MAC address or hostname, if MAC address is advertised
* SqPoller: Add support to look for entries whose servicing exceeded the poll period
* Junos: Fix interface parser to extract IPv6 address along with IPv4
* Run flake8 (a python linter) on all files and fix errors/warnings reported by flake8
* Fixed LLDP support for SONiC
* BGP assert bug fixes
* Fix address unique columns=vrf to return only VRFs
* Handle inconsistencies in output across various tables for errors (show, assert, unique, etc)
* Handle missing output in retrieving device config correctly (resulted in exception otherwise)
* Bug fixes to the anonymizer
* Security update to mkdocs (used to generate documentation, not used in code)
* Add tons of tests to catch inconsistencies in schema vs show output, regex, sqpoller and so on


## 0.15.5 (Oct 25, 2021)

Another bugfix release of the 0.15.5 release train. The main fix is the reworking of the network find algorithm.

* __network find__: (BREAKING CHANGE) The network find algorithm has been rewritten to work correctly when time is specified. We also got rid of the resolve-bond keyword and now always display the members of the port channel if outgoing interface is a port channel. We got rid of the "how" column, and added "type" column that indicates if the given address is connected as a bridge or a routed port. The members of a port channel if present are displayed in the "bondMembers" column.
* Improved BGP assert: To display a possible reason in case of a BGP session that's not established, and has a missing peer.
* Fix #312: We display the timestamp in the interface assert output, to make it consistent with the other assert outputs.
* Handle the case of a hostname or namespace specification not selecting any data correctly. Before this fix, a hostname that doesn't exist would result in displaying all hosts.
* Added more tests, and updated tests and data to match the poller updates from the earlier versions of this release.

__NOTE__: If you're installing Suzieq as a pip package, you'll have to install version 0.15.5.1 because of how pip dragged in an incompotible version of the pyparsing library resulting in random parsing errors. 

## 0.15.4 (Oct 18, 2021)

This is a largely a bug fix release of the 0.15.0 release. However, it does add one important foundational feature: support for parsers/commands based on NOS version.

* Support for multiple NOS versions: Different versions of a NOS produce either different outputs or sometimes even require different command names. One example that impacted Suzieq right away is Junos' QFX command for getting the LLDP neighbors. The post 19.1(?) release use "show lldp neighbors detail" to get the peer interface name, while older versions of Junos only require 'show lldp neighbors" for the same info. With this release, we can specify both commands with the versions they're relevant to, and Suzieq poller will pick the right command to use based on the version of the node it is polling. So, even in the same namespace, you can have two different versions of the same NOS, and the poller will pick the right command and parser to use for each version.
* Bug fix for proper use of start and end times: Many commands didn't properly apply the user-specified start and end times to the additional tables they called upon. For example, ```network find``` didn't use the start and end times when invoking arpnd or mac address tables, leading to the wrong output. This is fixed now across all commands.
* Bug fix for GUI Path: The swap source and dest button the GUI was not working correctly.
* Bug fix for interface assert: Interface assert was broken in certain cases such as a network without VLANs. Fixing that led to a far more improved interface assert than before. We now check subinterfaces also for consistency, Junos interfaces are supported and more. We added a new flag "ignore-missing-peer" to have the interface assert pass if no peer was found for an interface. For example, if you're peering with a device in a different administrative domain. By default, missing peers will be treated as assert failure. Using the ignore-missing-peer flag, the missing peer is reported, but the assert does not fail.
* More REST API fixes (interface assert was broken, for example). 
* Additional parsing fixes and tests: For example, we make the mac address table output consistent across MX/QFX now.
* Minor cleanups and typo fixes to help output.

## 0.15.3 (Oct 11, 2021)

This is a bug fix release with the following important changes:

* Fixed support for SoNIC: The SoNIC poller was broken due to lack of testing data. Thanks to Timo for help in fixing this.
* Fixed inconsistencies between REST API arguments and whats supported by the CLI. Added tests to catch such errors in the future.
* Improved Help: As per multiple user request, fixed help to work more intuitively. Now, "help", "help interface" and "help interface show" all work, with compleitions support.
* Support both singular and plural forms of the command now for routes, macs, interfaces.
* Fixed issues in parsing data across NXOS and EOS.
* Updated tests to handle more variations in test data, converting some errors into warnings. Updated pytest options to display warnings, and caught a few more bugs in tests.


## 0.15.1 (Oct 4, 2021)

This is a hotfix release for those who tried to install Suzieq via PyPi. There were multiple failures in the PyPi package that had been uploaded including some missing specifications for certain dependencies. (Issue #430).

## 0.15.0 (Oct 3, 2021)

This is a major release with tons of new features and important bug fixes.

* Added support for device inventory (see the new inventory verb). In this release, Arista EOS, Cisco's NXOS and Juniper Junos are the only supported NOS for this feature. See the __inventory__ command (or API)
* Added support for a virtual table called __network__. This is the first command you use to understand your entire network. It provides information about what namespaces data has been gathered for. In addition, it supports a new verb find that can be used to find to what router or switch a specified IP or MAC address is attached to; this traverses an L2 path as long as CDP/LLDP is used by the bridges in the L2 network. It can also be used to lookup BGP sessions by ASN. Moving forward, network find or maybe network search will become a central, and simple way to find all sorts of information about the network.
* __BREAKING CHANGE__. __top__ verb has been rewritten to work on any field (column) that is numeric.
* Fixes to ensure that timeouts don't end up declaring a device as dead forever, even if polling fails just once. This involved fixing the poller and the reader (see commits 854f02a0 and 1db819bf).
* Improved support for help. Every object now takes a help command to display help about all the verbs it supports. With the command= option, help displays additional information about the specified verb. Try out _network help_
* Updated GUI framework to streamlit version 0.87. Things should work better, and a little faster now. 
* GUI search now uses network find for an IP or MAC address. In addition, you can lookup unique values of MTUs, ASNs, VTEPs, VLANs, VNIs, as well as a listing of what set of hosts have a specific value of one of these tables. You can look at the help on the Search page for more details.
* __describe__ now works across all tables as a verb to display the schema of the saved data. Thus bgp describe lists the schema of the BGP table. tables describe table=bgp still works, but will be deprecated over time.
* Added ability to log to stdout. This feature is particularly useful for those running Suzieq on top of Kubernetes.
* Added __support for regex__ in specifying hostnames and namespaces. Start with "~" to indicate regex. "~spine.*" matches all hosts whose name starts with "spine", for example.
* Support for "!" operator is more consistent
* Searching by NOS version now works with "<, >..." and such operators. 
* Natural sorting of interface names is the default now. Thus Ethernet1, Ethernet2,..Ethernet10, Ethernet11 is displayed rather than the older Ethernet1, Ethernet10, Ethernet11.., Ethernet2, ...
* path, topology, and tables all now support all the common verbs supported by other tables. These include unique, summarize and top.
* The tables table has been rewritten to work like the other tables.
* The REST API has been updated to support all the new changes, and to support the verb top, which was not supported before.
* Improved support for Junos MX platform, thanks to Giovanni Pipito. This also includes support for etherchannel (bond) interfaces on any Junos platform.
* MAC Table support for Junos SRX devices.
* Handle CDP from older NXOS version such as 8.4.4.
* Updated parsers for OSPF and LLDP on older NXOS versions, like 8.4.4, thanks to Remco.
* Support viewing only the latest entry in a time window when providing start and end times instead of listing all the entries in that time range. The default behavior is unchanged. Use view=latest when both start and end times are provided to see the last valid values for a key in that time period. 
* Improved route and OSPF on IOS devices, thanks to Adrian Giacometti.
* A number of updates to the documentation from Adrian Giacometti and Eddie Lumpkin. Some additional developer doc updates by Luca Nicosia.
* uptime is now a proper augmented column of device table.
* Dependencies with security fixes have been updated.
* Several other bug fixes and code refactoring including discarding obsolete code.
* Over 500 additional tests have been added. 

## 0.14.2 (Aug 12, 2021)

This is a hotfix release if you use the REST API server. 

* Issue 403: REST API server fails to start in the docker container.
* This also contains a security update for the pywin32 library, which is an unused dependency within the GUI framework, streamlit. Nevertheless, the security update has been applied.
* We moved to python version 3.7.11. This happened in 0.14.1 itself, but we didn't note it in that release.

## 0.14.1 (Aug 10, 2021)

This release fixes a bunch of critical issues associated with release 0.14.0.

* Issue 399: IOSXE devices were not being recognized correctly
* Issue 400: Mlag parser fails when there are no configured server ports on EOS
* Issue 401: Secondary IP addresses on Arista interfaces causes interface parser to crash
* Fix Cisco's JSON time parser when only days were specified
* Fix Cisco's non-JSON time parser to handle various time formats provide by IOS platforms
* Fix NXOS VPC parser to not fail when orphan ports are not configured
* When specifying time as in "1 min ago" or "2 hours ago", the data returned was not consistent with
  what was returned when specifying precise times.
* Provide user-specifiable option to specify the logsize of the various suzieq loggers (REST, Poller etc.). 
  See the suzieq/config/etc/suzieq-cfg.yml file for logsize specification.
* Add tests to validate REST server startup with and without HTTPS support.
* Improved the container build process to ensure we don't rebuild everything when dependent libraries 
   have not changed. This results in smaller uploads and therefore faster pulls.
   
## 0.14.0 (Aug 1, 2021)

The major features in this release are the support for IOS/IOSXE network operating systems and a revamped REST API. This version also fixes a subtle but critical coalescer issue.

* __Support for IOS/IOSXE__: This release introduces support for IOS and IOSXE. All testing has been done using IOSvL2 (2019 version) and CSR1000v (16.11) images. Thanks to Rick Donato for his generous support for additional IOS testing. IOS and XE are mature operating systems with features and knobs galore.I obviously don't have the ability to test everything, but am happy to take fix bugs reported, take patch contributions and such. The support includes all the tables that Suzieq currently supports except for VXLAN and BFD support. 
* (_Breaking Change_)__Revamped REST API__: The v1 version of the REST API has been replaced by a newer v2 version. The fundamental difference is better support for the API tooling ecosystem. The v1 API accepted multiple values for a parameter as space separated strings. But it wasn't clear which query parameter accepted multiple values and which didn't by looking at the API. Some invalid parameters were silently ignored. Fixing all this is what led
to v2. A discussion on the Slack channel about the breaking change led to the conclusion that it was worth making this change now.
* Support for improved coalescing times: Instead of just 1 hour, 1 day etc., the coalescer now accepts much finer grained periods such as 10m, 2h etc. The coalescer also fires close to the top of the period. Originally, if you had a coalescing period of 1 hour and you started the coalescer at 7:59, the coalescer would coalesce the existing data and fire up at 8:59. But since it only coalesces whatever's in the 8:00-9:00 window when it wakes up, and since the clock is still at 8:59, it skips coalescing the entire hour's worth of data and only coalesces the data from 8-9 when it wakes up at 9:59. Thus, an additional hour's worth of data is always uncoalesced which can lead to bad query performance in the presence of a lot of data. The new version instead fires at 8, at 8, at 10 etc. to ensure all the data that can be coalesced is indeed coalesced.
* Support for additional filters for device: With device show, you couldn't filter by status, vendor, os etc. We now have support for all those filters.
* Improved LLDP support: LLDP show now tackles other interface subtypes such as mac address and ifindex (used by Junos as default), to fixup and display the more usable ifnames. OSPF assert is also more improved as a consequence.
* Improved algorithm for determining peer hostname in BGP: bgp show displays the peer hostname along with the peer IP. The algorithm used had very poor performance when the number of rows grew large (say with view=all). The new improved algorithm is orders of magnitude more efficient and uses less memory than the previous one.
* Updated dependent libraries such as asyncssh, fastapi and so on.
* Lots more new tests added and an improved and faster REST API test suite. We have 6K automated tests now.

## 0.13.0 (June 22, 2021)

This is a mostly technical debt fixup release, but it does include a couple of new features. If we had an LTS release, this release might be considered to be one. The GUI does have theming support now! 

Here is what is new in this release:

* Cleanup all the normalization values across all fields and tables. There were many fields where the values were not normalized (Up vs UP vs up vs linkUp, for example). This is by far the biggest things about this release, and users should rejoice at the simplification that results as a consequence (use of query-str becomes much more simple for example)
* Fix interface info retrieval (show in CLI/REST, get via Python API) to hide internal interfaces by default. NOS like Junos had a lot of internal interfaces (such as cbp, pimd, pime), which polluted the output. Use type='all' to see all interfaces in output of show/get or type='internal' to see only internal interfaces.
* Support for optional use of https with REST server. This was to make it easy to use a reverse proxy in fromt of the REST and GUI server to provide a uniform Web front end to both services (GUI/REST).
* Swagger API, fastAPI redoc, and openAPI URLs under REST have moved to /api/docs, /api/redoc and /api/openapi.json respectively. This is also to make writing a reverse proxy easier. 
* Improved docker-compose file with sample reverse-proxy configuration with Caddy. This is a contribution from a first time contributor, Ryan Merolle. Thank you, Ryan!
* Support for saving running config for SoNIC devices (thanks Senthil)
* Support for providing mac address in filters via multiple formats and capitalization (Issue #363). So, 44:01:02:FF:03:04, 4401.02ff.0304 etc are all supported wherever the keyword macaddr is used or in the address filter of the address table.
* Support for specifying connect timeout for connecting to devices via the connect-timeout parameter. (Fix #359)
* Added nexthop distribution info to route summary, so you can get a bird's eye view of nexthop distribution
* Added additional filters for topology command (Fix #243).
* Support for specifying column width in CLI (set col-width=100, for example). Fix issue #364.
* Add interface count with admin down in interface summary (Fix #360).
* Handling passing ssh config file correctly to lower functions (Fix #375), thanks to first time contributor, Drew Crutchfield.
* Added 1000+ new tests to catch all sorts of parsing errors. 
* Bumping up libraries due to security fixes (fastapi, uvicorn, urllib3, pydantic)
* Updated Streamlit GUI to 0.82.0. Theming support for GUI is now possible.


## 0.12.0 (May 28, 2021)

This list of features and bug fixes for this release include:


* Support for saving the running config of a device. We poll a device every hour for this, and save the existing running config if it has changed. The config is sanitized to exclude sensitive information like password (show running-config sanitized and equivalent commands). SoNIC is not supported for this in this release, will be adding it shortly.
* Support for topology. Topology is a virtual table, like path, that is used to construct the topology of the network, as seen from different perspectives. For example, you can see the BGP topology of the network, or the LLDP topology of the network etc. In other words, topology is the graph of the network where the edges (peers) are based on different fields such as routing protocol, LLDP and ARPND. We don't support topologies for virtual networks such as VRFs or VXLAN VNIs in this release.
* Support for numNexthops as an augmented column in routes. With this new column, you can look for routes with various ways to filter via query_str. 'numNexthops == 4' or 'numNexthops > 2' etc. (full command example: route show namespace=nxos columns = 'hostname vrf prefix nexthopIps numNexthops' query-str='numNexthops > 2' )
* Ports that are free i.e.have nothing connected to them are marked as notConnected for EOS, NXOS. Cumulus and JunOS to follow soon. This enables users to check for that specific state.* Support for getting NXOS L2 interface speed and MTU independent of the number of interfaces on the device. The command used thus far had a bug that caused the command the fail if there were more than 64 interfaces on the device (NXOS bug). The new version addresses that issue.
* device summary now lists the count of devices that are down.
* Various minor bug fixes for parsing info from EOS, especially BGP.
* Support for changing the directory where parquet files are stored via CLI. If you're in the CLI, you can use set datadir='<datadir>', where <datadir> is the directory you want to change to. Previously, you could do this only by quitting suzieq-cli and supplying a different config file on input.
* Additional stats in sqPoller table to help understand poller behavior.
* Support for Junos vSRX. This was just a device NOS string check (Issue #373)
* Updated python library pydantic to fix minor security alert reported by Github's dependabot

## 0.11 (Apr 6, 2021)

This is a mostly a repackaged 0.10 release, but now shippable as a python package as well. You can use pip install to install Suzieq. As a consequence, some of the directory structures (for config) have changed, and the suzieq config file format has been streamlined and made consistent so the variables appropriate to each component is present in the right hierarchy. The older config file will be subsumed and converted internally.

## 0.10 (Apr 1, 2021)

No, it isn't an April Fools release. There are several major features in this release. 

* **Platforms**: __Added support for IOSXR and Juniper SRX platforms__. EOS now supports VXLAN info (evpnVni table) and has support for SSH and REST. NXOS performance improved to use [json native instead of json]( https://www.cisco.com/c/en/us/td/docs/dcn/nx-os/nexus9000/101x/programmability/cisco-nexus-9000-series-nx-os-programmability-guide-release-101x/m-n9k-nx-api-cli-101x.html). You can see the supported platforms and tables [here](https://suzieq.readthedocs.io/en/latest/tables/).
* **Support for augmented columns**: Augmented columns are columns that are computed based on other columns, typically from the same table, but possibly from other tables as well. Examples of augmented columns includes peerHostname in case of OSPF, moveCount in MAC tables and so on. Details about augmented columns and their implementation can be found in this [doc](https://github.com/netenglabs/suzieq/blob/master/docs/developer/augmented-columns.md). From the user's perspective, an augmented column is indistinguishable from any other column. The benefit of augmented columns is that with the introduction as a column, different queries such as unique, finding frequency distribution etc. become natural.
* __Support for generalized query__. We store many key fields for each table. BGP stores 50+ different fields per session. Providing an individual filter per field is too cumbersome. In addition, there are fairly more combining of fields to create a more powerful filter that is hard to do with individual key/value filter fields. So, we added support for a generalized filter field where you can express complex filter fields via a generalized pandas query format. This [link](https://suzieq.readthedocs.io/en/latest/pandas-query-examples/) provides samples for some of the more common queries. Ask for help on the Slack channel if you're stumped.
* **Support for providing a password via an ENVIRONMENT variable**. Today, we support providing password via either a prompt on launching the poller or in the inventory file. This release adds support for reading the password from a user specified environment variable. Using the --envpass=<ENVVAR> when starting the sq-poller allows you to use this feature. 
* **Support for mac move**. You can now get a field called moveCount in the MAC table that allows you to see how many times a MAC has moved. You can filter MAC entries that have moved more than X times in a period, see all the different moves of a MAC (outgoing interface or remote VTEP change) in a given period, see frequency distribution of how the moves are (100 MACs moved 20 times, 5 MACs moved 10 times etc.)
* **Support for multiple address families in BGP**. In the initial releases, BGP table only supported looking up IPv4/IPv6 unicast and EVPN AFI/SAFI info. This version adds support for pretty much all the BGP AFI/SAFI. We normalize the AFI/SAFI names across all the NOS so you don't have to know every NOS' version of it. We've hopefully picked names that are sensible to all users. Please provide us feedback about this if the names are an issue for you. 
* Improved summarizations for BGP and a few other tables.
* Improved syntax checking of inventory file.
* Qualify search results in GUI with namespace.
* Tons of bug fixes in parsing info, analyzing info, path trace, coalescing and more.
* We've added a lot more tests.

## 0.9 (Feb 17, 2021)

The main feature of this release is the support for more efficient storage and providing fast, almost constant query times independent of the time window you're searching for (5 mins ago OR 5 mins a year back). There are a few other minor bug fixes. There's a new process called sq-coalescer that's running in the background. Its launched automatically by sq-poller. 

* Juniper commands now have "no-more" added to the end to prevent some older machines from blocking (Issue #314)
* device now has serial number and OS name (nxos, eos, cumulus etc.). This is in preparation for support of IOS-XR and IOS-XE.
* bgp show view=all was broken (Issue #318)
* Graceful termination of sq-poller on Ctrl-C or SIGINT (Issue #321)

## 0.8.7 (Jan 11, 2020)

A hotfix release to ensure REST server works. 0.8.6. broke the REST interface. 

## 0.8.6 (Jan 11, 2020)

This is another quick release to make path work well in more conditions including support for VXLAN L2 trace with EOS, reverse path check, handling NXOS vagaries like having interface names such as "vPC Peer Link" instead of the real peerlink interface name. We also added both in and out MTU to the output so that users can spot the issue in the path output itself.

The one additional feature we added was to allow users to specify the location and name of the SSL certificate and key files needed for the REST server. This feature was added thanks to Dennis Fanshaw working at a hyposcaler hyperbolic.

## 0.8.5 (Jan 4, 2020)

This is mainly improvements to path tracing, focused on debugging any issues with forwarding along the path. Visually, the way you can use path trace is far more interactive to troubleshoot than the first version. In the process of doing this, the release also found a bunch of data gathering issues with different NOS and fixed them, including capturing MTU on NXOS switched ports, fixing the mac table entries for Linux bridge so that the VLAN was properly derived for remote macs, getting the MAC address for Junos IRB interfaces and so on.

## 0.8 (Dec 14, 2020)

The three main features of the 0.8 release are the availability of a GUI, and the simplified experience of time, and Junos EX support. Here are the more detailed release notes:

* GUI support
* Simplified support of time.  You can specify time in English when querying by time. For example, '10 pm last night', or 'two days ago' or 'Jun 19' or 'two years ago'.
* Allow the user to provide the password for device login via a prompt rather than storing it in a file (--ask-pass option)
* Junos EX support. We've tested version 20.3R1.8.
* Display the admin state of an interface in interface show
* Fixed some bugs in parsing Junos EVPN information as well as interfaces
* Support for pandas query string in GUI and REST API. The CLI support for this will be in the next release
* Removed inconsistencies in storing interface oper state ('up', 'Up' were both present, for example).
* Updated the dependency libraries to newer versions.

Junos EX support is thanks to Andrea Florio.

## 0.7 (Nov 25, 2020)

There have a been a bunch of improvements in data gathering and making them consistent across NOSes in this release, along with improvements such as better summarizations, improved interface assert etc.

- Pager support within the CLI for longer entries
- Support for partial command specification. int sh completes to interface show
- Support for EVPN routes for EOS
- Path enhanced to support tracing from first hop switch and support for trunking ports
- Improved interface assert: match MTU, VLAN set, PVID, speed, IP address
- Improved OSPF assert, ignore admin down interfaces
- Markdown format output in both CLI and REST
- Allow specification of default poll period in config file. Saves laborious process of adding period to every resource file
- Filter assert outputs to only show whats failed, only  whats passed or all
- Improved VLAN summarize
- Fixed major bug in constructing mac table keys across various NOS
- Make summarize work with hostname qualifier
- JunOS route data normalization in the presence of OSPF unnumbered and EVPN routes
- Improved EVPN VNI info for JunOS
- SSH authentication improvements: Support for username/password keywords in inventory to handle values that may use URL reserved chars such as '.'. Eg, username dinesh.dutt is now supported via this method
- Anycast gateway MAC fix for SVIs with NXOS and EOS
- Improved filtering support for numerical fields
- ARP/ND entry fixes for Cumulus versions greater than 4.0
- Making interface data consistent across all NOS, support for portchannel interfaces in NXOS
- Test improvement in making pandas dataframe compare more robust
- Added 100 more tests

## 0.6 (Nov 5, 2020)

The most critical feature in this release is the support for a RESTful API. 

* Support for NXOS VPC and Arista's MLAG features
* Support for VLAN resource across all NOS: Juniper, Arista, Cisco and Cumulus. Unfortunately, this meant we had to throw away the existing Cumulus support and redo it to bring it in line with the other NOS.
* Support for prefixlen in route unique
* Support for Markdown as an output format. This is especially useful for chatbot support.
* Internal: Added 2K+ automated tests as part of testing REST that actually are tests of the underlying code for consistency and correctness across all resources.
* Fixed some bugs in path show with EVPN
* pandas version bumped to 1.1.4
* Bug fixes in writing ARPND data for NXOS
* Bug fixes to ensure all interfaces are associated with the right VRF in EOS
* Security fix: Bump cryptography version from 2.9.2 to 3.2 to fix some security issues as recommended by Github's dependabot.
* Fixed multiple bugs in underlying code for consistency of values passed and supported filters.
* UX Change: All protocol state is now flagged with the "state" filter, not the "status" filter. It takes specific values associated with the protocol, and the CLI offers completions for each.

## 0.5 (Sep 22, 2020)

This is a release with some major structural changes, and support for SONIC NOS.

* Support for SONIC NOS, thanks largely to Senthil Ganesan from Dell, with some additional assistance from Andrea Florio.
* Improved performance based on modified partitioning, and improved algorithms:
  * Read/Write Parquet uses the new dataset API
  - Improved predicate pushdown support with new dataset API for improved IO efficiency
  * We use vectorization and itertuples to support full Internet routing table with good performance. Thanks to Donald Sharp for this.
  * Row group size of 100000 and the ZSTD compression for better compression and read/write performance
* Schema evolution support. Now you won't need to throw away data with newer Suzieq releases. 
* (Alpha) Migration tool to help with migrating old data to new format
* Improved SSH security support including support for jumphosts, passphrase with private key, ssh config support. Thanks to Steve Dodd(idahood) for his help with testing and requesting the features.
* Support for complex Ansible inventory to retrieve username/password etc. via the ansible-inventory command output
* (Beta) Support for anonymizing data. At this time, it anonymizes hostnames, IP addresses and MAC addresses. It anonymizes the data gathered via --run-once=gather option of sq-poller, not the parquet data itself.
* Improved support for JunOS timestamps that caused some unnecessary data gathering in various scenarios.
* Improved and consistent support for filters based on '<, >, <=, >=, !=' including supporting these for filters that weren't supported before such as VLANs and MAC addresses
* Bug fixes to path show to handle VRR interfaces (in Cumulus) correctly

## 0.4.1 (August 23, 2020)

This is a hotfix release to fix the following two critical bugs in the 0.4 release:

* [Issue 237](https://github.com/netenglabs/suzieq/issues/237). JunOS interface poller had a bug that caused it to continue dumping the interface information gathered every polling interval even if nothing has changed. This causes the interface database to increase unnecessarily.
* The show commands had their column display order jumbled up instead of a well-known, fixed order.

Besides this, there was another bug fixed which ensured that we didn't use the transient, unmassaged fields in the computation of the difference between the current poller result from the result of the previous poll.

## 0.4 (August 18, 2020)

In addition to bug fixes, the new features in this release are:

* Support for vastly improved path command. You can get overlay plus undelay path traced, support for outgoing interface as well as incoming interface, a bunch of bugs fixed.
* Support for looking at JunOS based on model, junos-mx and junos-qfx. The main support in MX is support for gathering MAC address from VPLS. 
* Mac show now handles VPLS MAC instance filtering in addition to the existing filters. 
* Support for new table, FS, for file system. Support for gathering FS data from all supported platforms now: Cisco, Cumulus, Juniper, Arista and Linux servers. You can filter FS output based on mountpoint, used percentages.
* ``table describe`` now supports displaying any description associated with each field. Only path table has descriptions added in this release. But the code is such that a user can edit the schema file, add the description and have the result show up without writing any code.
* **ALPHA FEATURE** topology table continues to see improvements and additions. We've added support for displaying ARP neighbors in the topology view.


## 0.3 (July 15, 2020)

First release with third-party contributions! Vastly improved support for realistic NXOS data center deployments. Besides 32 closed bugs, main enhancements include:

* Improved EVPN assert to handle cases of using routed multicast underlay instead of ingress replication. This includes checking for consistency of multicast groups for a VNI across nodes.
* NXOS support for EVPN requires version 9.3.3 or later as there's no command to get certain info about all VNI, only by specific VNI values.
* Improved EVPN show and summarize to include more meaningful outputs.
* Improved BGP and OSPF assert. BGP assert especially handles a few more cases such as when peering is not over directly connected interfaces. 
* **ALPHA feature** Support for topology as a first class resource. Try topology show and topology summarize. This is still work in progress.
* Support for the poller to gather data from nodes and saving them to a directory. You can then run the poller to read this directory to build the output files.

## 0.2.1 (June 18, 2020)

The main issue was fixing a bug in Junos BGP data capture that got missed in the tests. This is issue #170. We also fixed #169 listed below as part of release 0.2. However, another Junos bug is still open

* [Bug #176](https://github.com/netenglabs/suzieq/issues/176): BGP uptime is not properly captured for Junos.

## 0.2 (June 18, 2020)

The **main features** of this release are **IPv6 support** and support for **extracting data out of NXOS and Junos** devices. A few bugs have been fixed. **The parquet data format has changed and will change for one more release before we start supporting an evolving schema format.** If you have significant or important data saved with the older release, please reach out to us for specific assistance.

More specific release notes and caveats emptor are:

* Not all asserts work with Junos devices because of the LLDP information provided as a result of the default configuration. 
* No testing has been done at scale. Please reach out to us if you're running into problems with polling either a large number of devices or pulling a lot of data (routes, macs, arp/nd usually) from a single device. If you don't run into any problems doing so, please reach out to us to let us know about your success.

* [Bug #169](https://github.com/netenglabs/suzieq/issues/169) which shows an incorrect error message in the poller log file
