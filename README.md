[![Build Status](https://travis-ci.org/netenglabs/suzieq.svg?branch=master)](https://travis-ci.org/netenglabs/suzieq)

# Suzieq

Would you like to be able to easily answer trivial questions such as how many unique prefixes are there in your routing table, or how many MAC addresses are there in the MAC tables across the network? How about more difficult questions, such as what changes did your routing table see between 10 pm and midnight last night, or which of your nodes have been up the longest, or which BGP sessions have had the most routing updates? How about being able to answer if your OSPF (or BGP) sessions are working correctly, or is all well with your EVPN? How about a quick way to determine the amount of ECMP at every hop between two endpoints? Do you wish you could easily validate the configuration you deployed across your network? 

Do you login to every network node you have to figure out answers to a questions like these? Do you then struggle to piece the information together into a consistent whole across the various formats provided by various vendors? Do you wish you had an open source, multi-vendor tool that could help you answer questions like these and more?

If you answered yes to one or more of these questions, then Suzieq is a tool that we think will be interesting to you. 

**Suzieq** is both a framework and an application using that framework, that is focused on **improving the observability of your network**.  We define observaility as the ability of a system to answer either trivial or complex questions that you pose as you go about operating your network. How easily you can answer your questions is a measure of how good the system's observability is. A good observable system goes well beyond monitoring and alerting. Suzieq is primarily meant for use by network engineers and designers.

Suzieq does multiple things. It collects data from different devices and systems. It normalizes the data and then stores it in a vendor independent way. Then it allows analysis of that data. 

We believe Suzieq is novel because it is a disaggregated framework that allows you to independently pick:
* how you gather your data (agentless or agent-based)
* how you store your data
* how you interact with the data i.e. how you ask the questions and how you see the answers.

With the applications that we build on top of the framework we want to demonstrate a different and more systematic approach to thinking about networks. We want to show how useful it is to think of your network holistically.

In this very early release of Suzieq, we've chosen some answers for the framework to get the ball rolling. 
* We gather data using an agentless model using either SSH or REST API as the transport. 
* We normalize the data into a vendor-agnostic format.
* We store all data in files using the popular big data format, Parquet. 
* All the analysis are exposed either via a CLI or via Python objects. The output can be rendered in various formats from plain text to JSON and CSV.
* The analysis engine used in this release is pandas.

**We support gathering data from Cumulus routers, Arista routers, and Linux servers.**

We are just getting started with Suzieq. As befitting an early release, what you see is only a brief demonstration of what this approach can bring about. We've many, many ideas to implement in our upcoming releases, but we wanted to get this out so that people can start using it. And start understanding their networks to solve problems, validate or to make changes.

You can join the conversation via [googlegroups](https://groups.google.com/d/forum/netenglabs-suzieq).

We're also looking for collaborators to help us make Suzieq a truly useful multi-vendor, open source platform for observing all aspects of networking. Please read the [collaboration document](./CONTRIBUTING.md) for ideas on how you can help. 

## Quick Start

We want to make it as easy as possible for you to start engaging with Suzieq. To that end, the quickest way to start is to download the docker image from github and also download the data we've already gathered for the 18 or so network scenarios from the [github](https://github.com/netenglabs/suzieq-data) repository associated with Dinesh's book, Cloud Native Data Center Networking. You can then use the introductory documentation to start exploring the data.

- ```git clone https://github.com/netenglabs/suzieq-data.git```
- ```docker run -itd -v /home/ddutt/suzieq-data/cloud-native-data-center-networking/parquet-out:/suzieq/parquet --name suzieq ddutt/suzieq:latest```
- ```docker attach suzieq```
- ```suzieq-cli```

When you're within the suzieq-cli, you can run ```device unique columns=namespace``` to see the list of different scenarios, we've gathered data for.

Note that in the docker run command above, the directory name /home/ddutt/suzieq-data/... used assumed that the git clone of suzieq-data was done in the directory /home/ddutt. In other words, the host path name used in the -v option should be the **absolute path of the directory**, not the relative path.

From here on, you can follow the [preliminary documentation](./docs/analyzer.md) for further exploration. If you wish to run the poller to gather data from your network, you can do so via the instructions [here](./docs/poller.md). 

We're working on putting up more extensive documentation for every aspect of Suzieq: as a user, and as a contributor. We hope to be done with that by the end of this week.

