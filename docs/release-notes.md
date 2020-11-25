## Release Notes

## 0.7 (Nov 25, 2020)

There have a been a bunch of improvements in data gathering and making them consistent across NOSes in this release, along with improvements such as better summarizations, improved interface assert etc.

- Pager support within the CLI for longer entries
- Support for partial command specification. int sh completes to interface show
- Support for EVPN routes for EOS
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
- SSH authentication improvementss: Support for username/password keywords in inventory to handle values that may use URL reserved chars such as '.'. Eg, usename dinesh.dutt is now supported via this method
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




