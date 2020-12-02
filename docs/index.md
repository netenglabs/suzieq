# Suzieq

**Suzieq** is both a framework and an application using that framework, that is focused on 
**improving the observability of your network**.  We define observability as the ability of a system to 
answer either trivial or complex questions that you pose as you go about operating your network. How easily 
you can answer your questions is a measure of how good the system's observability is. A good observable 
system goes well beyond monitoring and alerting. Suzieq is primarily meant for use by network engineers and designers.

Suzieq does multiple things. It collects data from different devices and systems. It normalizes the data and 
then stores it in a vendor independent way. Then it allows analysis of that data. 

We believe Suzieq is novel because it is a disaggregated framework that allows you to independently pick:

 * how you gather your data (agentless or agent-based)
 * how you store your data
 * how you interact with the data i.e. how you ask the questions and how you see the answers.

With the applications that we build on top of the framework we want to demonstrate a different and more 
systematic approach to thinking about networks. We want to show how useful it is to think of your network holistically.

In this very early release of Suzieq, we've chosen some answers for the framework to get the ball rolling. 

 * We gather data using an agentless model using either SSH or REST API as the transport. 
 * We normalize the data into a vendor-agnostic format.
 * We store all data in files using the popular big data format, Parquet. 
 * All the analysis are exposed either via a CLI or via Python objects. The output can be rendered in various formats from plain text to JSON and CSV.
 * The analysis engine used in this release is pandas.

**We support gathering data from Cumulus, Arista, JunOS and NXOS routers, and Linux servers.** We gather:

* Basic device info
* Interfaces
* LLDP
* MAC address table
* MLAG (only for Cumulus and EOS at this time)
* Routing table
* ARP/ND table
* OSPFv2
* BGP (v4 unicast, v6 unicast and evpn AFI/SAFI)
* EVPN VNI info (not for EOS at this time)

We are just getting started with Suzieq. As befitting an early release, what you see is only a brief 
demonstration of what this approach can bring about. We've many, many ideas to implement in our upcoming 
releases, but we wanted to get this out so that people can start using it. And start understanding their 
networks to solve problems, validate or to make changes.

You can join the conversation via [slack](https://netenglabs.slack.com). Send email to Dinesh or Justin with the email address to send the Slack invitation to. 

We're also looking for collaborators to help us make Suzieq a truly useful multi-vendor, open source platform 
for observing all aspects of networking. Please read the [collaboration document](./CONTRIBUTING.md) for 
ideas on how you can help. 



