## Release Notes

## 0.2.1 (June 18, 2020)

The main issue was fixing a bug in Junos BGP data capture that got missed in the tests. This is issue #170. We also fixed #169 listed below as part of release 0.2. However, another Junos bug is still open

* [Bug #176](https://github.com/netenglabs/suzieq/issues/176): BGP uptime is not properly captured for Junos.

## 0.2 (June 18, 2020)

The **main features** of this release are **IPv6 support** and support for **extracting data out of NXOS and Junos** devices. A few bugs have been fixed. **The parquet data format has changed and will change for one more release before we start supporting an evolving schema format.** If you have significant or important data saved with the older release, please reach out to us for specific assistance.

More specific release notes and caveats emptor are:

* Not all asserts work with Junos devices because of the LLDP information provided as a result of the default configuration. 
* No testing has been done at scale. Please reach out to us if you're running into problems with polling either a large number of devices or pulling a lot of data (routes, macs, arp/nd usually) from a single device. If you don't run into any problems doing so, please reach out to us to let us know about your success.

* [Bug #169](https://github.com/netenglabs/suzieq/issues/169) which shows an incorrect error message in the poller log file




