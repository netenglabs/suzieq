# Release Notes

## 0.19.1 (Sep 6, 2022)

This patch release for the 0.19.0 release includes the following important fixes:

* Fixes bug in path whereby an address such as 10.1.1.110 was incorrectly matched with 10.1.1.1 causing path problems
* Fixes inconsistent use of "!" in filtering by device version string
* Fixes intermittent crashes in device show (or the status page in the GUI) when using columns=*
* Fixes incorrect hostname setting on NXOS devices in some conditions when the hostname is a hostname that includes the domain name
* Add missing keyword query-str to path commands

## 0.19.0 (Aug 22, 2022)

The 19th release of SuzieQ contains bug fixes and improvements to key functionalities such as the REST API and endpoint tracker. Here's a detailed list of key features of this release:

* **Much improved Endpoint Tracker**: The endpoint tracker now displays endpoint movement accurately across all network OS. Its also faster. There are many other enhancements to endpoint tracking which we'll cover in a blog post separately.
* **Vastly improved REST API performance**: Due to a bug in the code, the REST API handled only one request at a time. This has been fixed.
* **EVPN VNI Assert Improved**: The EVPN VNI assert has been improved and cleaned up, and become faster too. 
* **Fix/improve VLAN filtering**: VLan filtering with interfaces such as ```interface show vlan="> 25"``` did not work correctly. This has been fixed, and coupled with support for in-between, allows for more powerful searching by VLAN
* **In Between Semantics for Numeric Fields**: You can now use ">25 <50" to mean all numbers between 25 and 50 (not inclusive).
* **Gather only connected routes for Junos MX**: Juniper MX devices have difficulty displaying the routing table (with JSON) in a short time when dealing with Internet size routing tables. This has led to some frustration on the part of users using SuzieQ to gather data from MX devices. For now, we only gather connected (or direct) routes on MXes to mitigate this problem. This is a **breaking change** if you're using SuzieQ with MX currently. Reach out over Slack if this is an issue for you, and we can tell you how to restore the old behavior for your specific setup.
* **Netbox Multi-Tag Support**: We support the use of multiple tags (with complex OR/AND logic) to identify devices that SuzieQ should poll.
* **Making string match consistent**: We use ! to signify not equal to. So, "!leaf01" means a string that's not equal to leaf01. When it came to regexp however, we used ~! to signify a not equal to of the regexp. To be consistent, we need to say !~. Now you can consistently use ! as in ifname="!Ethernet1/1" as well as ifname="!~Ether.*". 
* Poller Parser Fixes
* **Handling router MAC in NXOS**: NXOS creates the same MAC addr/VLAN entry for both the SVI and the CPU. We didn't distinguish this case and so while we wrote both entries, the read displayed only one of them, and which of the two we did was unpredictable. This fix displays both entries with the flag "router".
* Cumulus devices now recover from being dead
* Updates to various libraries used, either because newer ones were available or due to security updates.

And many more bug fixes, new tests and test fixes.

## 0.18.0 (June 21, 2022)

This 18th release of SuzieQ contains significant improvements to all the various NOS parsers, but especially IOSXE (more versions and more platforms supported now) and versions of NXOS older than 9.3.x. We've also added support for throttling the rate of requests SuzieQ poller issues to prevent overrunning AAA Servers. A more detailed list of features and critical bug fixes follows:

* **Improved support for IOSXE** (more versions, more platforms).
* **Support for all NXOS versions**, those before 9.3.x which had no ```json native``` support.
* **Improved parsing support for most NOS**.
* **Support for rate limiting requests to AAA Servers**. See the poller documentation for details.
* **Additional fields for device table added**. You can now get a distriubution of the common causes for device reboots.
* **Fixed bug in supporting multiple schema versions of a table**. This was only a bug in reading, writing was correct.
* **New command, namespace, to get information about namespaces**. This deprecates network show/summarize/unique/top. Endpoint tracker is still at network find.
* **Improved OSPF assert**, to handle non-p2p interfaces better.
* **Removed all commands that required use of Linux shell on NOS**. This is for NXOS and EOS.
* **Vastly improved Node discovery**. We wouldn't reattempt node discovery if it failed more than twice, improved log messages and more.
* **Improved Path Support**. We now handle recursive routes more effectively and so can be used in more than EVPN scenarios.
* **Vastly faster endpoint tracker**.
* Support accepting MAC in any format (such as 00-AA-BB-CC-DD-EE or 00AA:BBCC:DDEE etc.)
* Added tons of new tests including importantly to catch more parsing errors
* Updated libraries including those with security updates.

The one person to thank from the user community for this release is Andy Miller. Thanks Andy, this release wouldn't have been what it is, if it wasn't for you.


## 0.17.2 (Apr 28, 2022)

This is the second patch release of the 17th release. The main issues that are fixed in this release are:

* A thorough refactoring of how communication with devices is done to enable proper support of the various options of connecting to devices. For example, we did not handle inactivity timeouts with IOSXE devices correctly, nor did we appropriately flag the specification of REST transport without specifying device type, or handle IOS/XE devices if privilege escalation was required even to do show version. IOS/XE devices that do not support running show version without privilege escalation require users to specify the device type via devtype= parameter against the device.
* In some situations, path would crash or the GUI status page wouldn't come up due to a bug in how the VLAN was determined for an interface. 
* For netbox inventory type, specifying the transport type would cause a crash.
* We now display an unsupported device type via device show.

## 0.17.1 (Apr 12, 2022)

This patch release for version 0.17.0 fixes a bunch of deployment issues that 0.17.0 introduced due to changing the default user inside the container from root to suzieq. Besides this, the following bug fixes and an enhancement are part of this release:

* **Active column displayed with +/-**: Whenever you request data between two time periods or request all records via view='all' option, the active column was not displayed/returned. This meant, a user couldn't figure out if a record was added or deleted. We now return the active column and in the CLI, we display the active column as '+' (for added) or '-' (for deleted) with each record. The REST, JSON, non-human as well pythonic API return True (for records added i.e. active) and False for deleted (or not active) records.
* Bug fix to improve query response with time: Due to a bug in the code, the queries were very slow in returning the data when asked for data back in time.
* Bug fix to display VLAN info consistently: Not every NOS returns the native VLAN (or PVID) of a port with the same command. Therefore, we weren't displaying the correct VLAN info even though we had it.
* Bug fix to handle interface assert: Interface assert was incorrectly removing certain interfaces for interfaces associated with Junos-based devices.
* Bug fix to set VLAN correctly for Junos-based devices: The poller incorrectly marked the VLAN as 16285 for interfaces such as lo0.16385. We now ensure that the VLAN is never > 4095, and set it to zero if it is.
* Bug fix in filtering with remote DB: Namespace/hostname filters weren't working correctly when used with the remote DB.
* Bug fix in passphrase keyword assumed and documented: The correct keyword is key-passphras
* Bug fix for jumphosts when jump host key was not specified
* Added code to notify users with a proper message due to permission problems inside the container.
* Updated documents to reflect the reality of 0.17.1.
* Improved tests 

## 0.17.0 (Mar 29, 2022)

The 17th release of SuzieQ comes with the following new features and bug fixes. The main improvements are in the area of more accurate database records, improved user experience via GUI and remote DB, imrpvoed platform support for IOSXE, NXOS and EOS, and a significant code refactoring to make the codebase consistent and simple. This is in addition to numerous bug fixes, and the addition of numerous tests. You can say this is the first release that starts to target segments outside the datacenter, specifically the campus.

* **Stable, Powerful GUI**: The GUI features the easily filterable and searchable tabular display based on the popular ag-grid framework. The version introduced in 0.16.0 was unstable. With this release, use the GUI to easily spot errors, search and analyze data.
* **No duplicate records on poller restart**: Till this release, whenever the poller was restarted, the poller added new records that were duplicates of the existing records, because we didn't compare the state of what we have in the database on poller restart. This release fixes this major annoyance, allowing people to look at changes much more easily. Snapshots now only record changes from the existing data in persistent storage, making looking for changes easier.
* **Improved IOSXE Support**: This version has been tested on many different versions of IOSXE on platforms ranging from Cat4K and 6K to Cat 3850 and Cat9K. There are many versions and platforms that support IOSXE, so support continues to evolve and improve. If you run into any pronlems, please report them. We also support looking at the inventory on IOSXE devices. Thanks to Andrea FLorio and Claudia de Luna for this and other IOSXE fixes.
* switchport support** SuzieQ's use is spreading beyond the datacenter into campus. As such, users requested the ability to see the switchport mode--access, trunk etc.--of an interface along with the native VLAN and the list of active, allowed VLANs on an interface. This is now supported. Use column names portmode and vlanList to see the switchport mode and list of allowed, active Vlans on a trunk interface. For example, interface show columns='hostname ifname state portmode vlan vlanList'
* **Support for Privilege Escalation**: In keeping with the campus use and support for older devices, escalation privielege support is an important feature. This involves using the command enable and a password to run in a privileged mode to execute any commands. This is now supported for IOSXE. Use the keyword enable-password with the same available options (plain and env) to provide the password.
* **Support for slower devices** Many older devices, running IOS/XE, run relatively slowly compared to the more modern OSes such as NXOS, EOS and Cumulus. To support such devices, we support a keyword, 'slow-host' which is defined under the devices section of the inventory and if set to True, SuzieQ poller throttles the rate at which it sends commands to the device.
* **Netbox API token as Environment Variable**: Many users consider the Netbox API token as a secret and do not wish to provide it in clearcase. So like other passwords 
* **4b ASN Support**: We didn't handle 4B ASNs provided in asdot format. We can now display the ASNs in asdot format. Use the column name asdot to see this.
* **Improved Topology**: You can now view the topology for a given VRF, an AFI-SAFI, an area and so on. Look at the supported keywords via ``help topology show``
* **Remote DB Improvements**: Many commands didn't work correctly when using a remote database. This is now fixed largely due to the testing by Rick Donato. Thanks Rick.
* **Improved EOS support**: We improved the support for EOS by fixing a bunch of parser errors with newer versions, and some older uncaught bugs. We now support EOS versions from 4.20 all the way to the latest 4.27.1
* **Improved asserts**: All asserts have been improved with additional functionality and bug fixes.
* **Scale testing**: Much of the code from the poller to analysis has been tested at scale, with over a 1000 devices.
* **Faster Route**: Very large route tables can be operated upon much more quickly, the difference can be several orders of magnitude depending on the routing table.
* **Path trace Improvements**: Path trace supports destination address not being in the network tables. We'll trace as far as we can.
* **Inventory Validation**: We now validate the inventory and print out helpful error messages about the errors.
* Blacklisted services topmem, topcpu and ifCounters: These three tables were not being used anyway. We'll reintroduce support when we can do something useful with them. 
* Fix sqpoller stats and description: We now show the poller stats with the max and min updated for every poller write period, which is either 5 min or the poll period, whichever is longer.
* Massive technical debt fix to ensure we don't suffer from inconsistencies when users use different filters, columns and so on. There are an enormous number of features supported in SuzieQ, and ensuring consistent operations across all of them when the code evolved organically meant we had to do a massive refactoring to make the code base simpler and consistent.
* We added hysterisis to marking a record dead. If we cannot reach a device today on a poll, we promptly mark all the records as deleted. This can cause unnecessary fluctuations in the records due to temporary network glitches. To avoid this, we mark a record as deleted only if we're unable to communicate with the device for 3 consecutive times. This naturally does not apply to marking non-existent records dead on poller restarts.
* Rename assert result field: The field called status in the assert output is now called result to avoid conflicts with fields called status in tables such as device. This is a __breaking change__.

## 0.16.0 (Jan 15, 2022)

This is the 16th release of Suzieq, with many new and useful features. Refer to the release notes for 0.16.0b1 and 0.16.0a1 for details. In addition to those features and bug fixes, this release has the following changes compared to 0.16.0b1:

* **Improved GUI Support** The new GUI had a bunch of critical bugs. This version fixes most of them. Refer to the caveats section of the GUI document for issues using it especially with the experimental feature enabled.
* **Breaking Change** Network find was broken in some cases and this has been addressed correctly. With this change, you can now get the output even if the MAC address has been aged out. This update adds a new column, l2miss, that is True if the MAC address was found in the L2 table, else false.
* You can specify a port to start the GUI on, if you can't use the default 8501.
* use-stdout for the logger is honored even if multiple poller instances are launched.
* Address table had a bug with the VRF field support thats been fixed.
* Lots more tests
* Made all the help messages associated with keywords in the CLI consistent, and clearer.

Thanks to Claudio Lorina, Claudio Usai, Luca Nicosia and Andrea Florio for their awesome work in getting this release out. This is the first release in a long time that has a ton of work done by developers other than myself.

## 0.16.0 beta (Jan 7, 2022)

This release adds a bunch of major features on top of the alpha release set. 

* **New GUI**: There's a new way to sort/filter information in the GUI without having to know any pandas or fancy SQL. Check out the Xplore page for more info. One limitation with the beta release: Entire rows are not highlighted in case of a bad status, only the cell (for example only the state column in interfaces table is highlighted if down, not the entire row)
* **Snapshot Mode**: A common use case is wanting to run the SuzieQ poller in snapshot mode i.e. run once over all supported tables over all devices in the inventory, update the parquet DB and terminate. People who used this had to resort to a slightly complicated sequence of steps to achieve their goal. Now, add --run-once=update option to the sq-poller command, and you get the snapshot mode behavior. 
* Filters applied to all verbs: Before this release, you couldn't apply filters to any command except show. For example, you couldn't get summaries over interfaces with an MTU > 9200 or BGP IPv4 unicast sessions or routes populated with BGP etc. Now, a table's filters are applicable to all commands associated with that command.
* **Polling from a local folder**: If you can't run the SuzieQ poller for whatever reason, but have a directory full of show command outputs from a set of devices and want this to be used to update the Suzieq database so that you can run all your favorite suzieq commands, it is now possible with the sq-simnodes program. More details can be found on [the documentation page](https://suzieq.readthedocs.io/en/0.16.0/simnode/).
* **Improved support for IOSXE devices**: including Catalyst 4509, Catlyst 9300, Catalyst 9500 and more. 
* **QFX10K Support**: Added support for Junos QFX10K platforms. QFX10K platforms are not like QFX5K platform, they're a hybrid between QFX and MX. This is now handled correctly.
* Poller now honors use-stdout: True in the config file.
* Use hostname instead of hostnamectl for determining Cumulus and Linux hostnames (Issue #530).
* You can see the Suzieq version via suzieq-cli version OR suzieq-cli -V. Same -V option can be used for the poller, and rest server. You can get the same info via the About option from the Menu in the GUI

A bunch of other additional bugs have been fixed. Thanks to Claudia de Luna and John Howard for their awesome assistance in getting this release out.


## 0.16.0 alpha (Dec 24, 2021)

This release has some major new features, and some breaking changes. Please note these changes before using Suzieq. This is an alpha release and so we expect there to be bugs. Please test and provide feedback via Slack or bug reports. The new features were the ones selected by the community as the ones they most cared about.

* Palo Alto Networks Firewall support: We've added support for this new platform. Support today is only when running the firewall in L3 mode, with support for only BGP protocol. We hope to add support for OSPF protocol before the final release. Please look at the [guide](./panos-support.md) for more details on using this feature.
* Netbox inventory support: We support pulling configuration directly from Netbox now. Netbox is the second of many plugins that we'll support for pulling inventory information. The first is Ansible. 
* **BREAKING CHANGE**: The entire inventory support has been redone. The old poller options of -D and -a are no longer supported. Inventory specification is now done in a more modular fashion with profiles. Please look at the inventory format on the [documentation page](./inventory.md). This page also includes instructions on migrating to the new format.
* CLI Support for Remote Data: Its now possible to use the CLI with a REST backend to transparently support running the CLI from say your laptop, while the data itself resides on a remote server. Please look at the [documentation](./remote-cli.md) for more details on configuring this.
* Support for breaking up the inventory across multiple pollers automatically. You can now specify the number of pollers when launching the poller, and we'll spin up the appropriate number of worker pollers and break up the inventory into equal sized chunks across these pollers.
* Enhanced filter support for all commands: Thus far, filters were largely only supported for show commands. Now, we've extended support for using the same filters across all commands. See route summaries based on the protocol, or look at device summaries based only on specific models, and so on.
* Fix Issue 476: Juniper BGP sessions which have AFI/SAFI strings such as inet-labeled-unicast are now correctly parsed.
* Support for seeing all interface addresses that much a subnet, or all ARP entries that match a subnet.
* unique verb now assumes a default column for each table that makes sense for that table. If no column is specified, this default column is assumed.

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
