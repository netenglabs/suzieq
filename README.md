[![Build Status](https://travis-ci.org/netenglabs/suzieq.svg?branch=master)](https://travis-ci.org/netenglabs/suzieq)

# Suzieq

Suzieq is an application focused on observability for IP networks: The primary goal is enable network operators and designers to understand their network holistically as a system. Suzieq gathers data and then allows analysis of the data in interesting ways.

Suzieq does multiple things. It collects data from different devices and systems. 
It normalizes the data and then stores it in a vendor independent way. Then it allows analysis of that data.
Suzieq has a pretty novel way of describing how to collect the data via various tools. We want to be
as agnostic as possible so that we can easily get all the necessary data in one place.

What does Suzieq do that is different from just logging into a device and getting the data?
1. It collects data from all devices and puts it in a central place.
2. It collects multiple pieces of data from each device.
3. It collects data from multiple vendors and normalizes it.
4. It collects data over time so that you can view changes over time.

By using each of these dimensions, we can easily build interesting applications that help understand
networks in way that is much easier. 

With the applications that we build on top of the framework we want to demonstrate a different
and more systematic approach to thinking about networks. We want to show how useful it is to think
of your network holistically. 

Suzieq data is focused on [Pandas DataFrames](https://pandas.pydata.org/pandas-docs/stable/getting_started/dsintro.html)
Everything returned by the analysis engine is a dataframe, which allows us to have a really nice abstraction
to build applications on.

For now, all the analysis are exposed either via a CLI or via Python objects. The output can be rendered in various formats from plain text to JSON and CSV.

We are just getting started with Suzieq. What you see in this early release are only a brief demonstration of what this approach can bring about. This is a very early release. We've many, many ideas to implement in our upcoming releases, but we wanted to get this out
so that people can start using it. And start understanding their networks to solve problems, validate or to make changes.

We're also looking for collaborators to help us make Suzieq a truly useful multi-vendor, open source platform for observing all aspects of networking. You can reach us either via LinkedIn or via email at thenetworkelegant AT gmail.

## Quick Start

The quickest way to start is to download the docker image from github and also download the data we've already gathered for the 18 or so network scenarios from the [github](https://github.com/netenglabs/suzieq-data) repository associated with Dinesh's book, Cloud Native Data Center Networking. You can then use the introductory documentation to start exploring the data.

If you wish to run the poller to gather data from your network, you can do so as well following the instructions [here](./poller.md).

- git clone https://github.com/netenglabs/suzieq-data.git
- docker run -itd -vsuzieq-data/cloud-native-data-center-networking/parquet-out:/suzieq/parquet-out --name suzieq 
- docker attach suzieq
- suzieq-cli

From here, you can follow the preliminary documentation [here](./prelim.md).

