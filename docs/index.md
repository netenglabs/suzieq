# SuzieQ

[**SuzieQ**](https://github.com/netenglabs/suzieq/) is the first open source, multi-vendor network observability platform application. It is both a framework and an application using that framework, that is focused on
**improving your understanding of your network**.  We define observability as the ability of a system to
answer either trivial or complex questions that you pose as you go about operating your network. How easily
you can answer your questions is a measure of how good the system's observability is. A good observable
system goes well beyond what is normally considered monitoring and alerting. SuzieQ is primarily meant for use by network engineers and designers.

SuzieQ:

* [Gathers data](https://suzieq.readthedocs.io/en/latest/poller/) using an agentless model using either SSH or REST API as the transport. We gather data from routers, bridges and Linux servers. We support gathering data from Arista EOS, Cisco's IOS, IOS-XE, and IOS-XR platforms, Cisco's NXOS, Cumulus Linux, Juniper's Junos(QFX, EX, MX and SRX platforms and Evolved OS), Palo Alto's Panos (version 8.0 or higher) and SoNIC devices, besides Linux servers.
* Normalizes the data into a vendor-agnostic format.
* Stores all data in files using the popular big data format, [Parquet](https://parquet.apache.org/).
* Exposes via a CLI, [GUI](https://suzieq.readthedocs.io/en/latest/gui/), a [REST API](https://suzieq.readthedocs.io/en/latest/rest-server/), or via Python the analysis of the data gathered using easy, intuitive commands. The output can be rendered in various formats from plain text to JSON, CSV and Markdown.

With the applications that we build on top of the framework we want to demonstrate a different and more systematic approach to thinking about networks. We want to show how useful it is to think of your network holistically.

**To get information about the enterprise version of SuzieQ, visit the Stardust Systems (website)[https://www.stardustsystems.net/]**.

You can join the conversation via [slack](https://netenglabs.slack.com). Send email to Dinesh with the email address to send the Slack invitation to.

We're also looking for collaborators to help us make SuzieQ a truly useful multi-vendor, open source platform
for observing all aspects of networking. Please read the [collaboration document](https://github.com/netenglabs/suzieq/blob/master/CONTRIBUTING.md) for
ideas on how you can help.
