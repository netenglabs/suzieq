# Suzieq

**Suzieq** is a network observability tool. It is both a framework and an application using that framework, that is focused on 
**improving your understanding of your network**.  We define observability as the ability of a system to 
answer either trivial or complex questions that you pose as you go about operating your network. How easily 
you can answer your questions is a measure of how good the system's observability is. A good observable 
system goes well beyond what is normally considered monitoring and alerting. Suzieq is primarily meant for use by network engineers and designers.

Suzieq does multiple things:

* We [gather data](https://suzieq.readthedocs.io/en/latest/poller/) using an agentless model using either SSH or REST API as the transport. We gather data from routers, bridges and Linux servers.
* We normalize the data into a vendor-agnostic format.
* We store all data in files using the popular big data format, ]Parquet](https://parquet.apache.org/). 
* All the analysis are exposed either via a CLI, [GUI](https://suzieq.readthedocs.io/en/latest/gui/), a [REST API](https://suzieq.readthedocs.io/en/latest/rest-server/), or via Python. The output can be rendered in various formats from plain text to JSON and CSV.
* The analysis engine used in this release is pandas, though we have prototyped with other analysis engines.

With the applications that we build on top of the framework we want to demonstrate a different and more 
systematic approach to thinking about networks. We want to show how useful it is to think of your network holistically.

You can join the conversation via [slack](https://netenglabs.slack.com). Send email to Dinesh or Justin with the email address to send the Slack invitation to. 

We're also looking for collaborators to help us make Suzieq a truly useful multi-vendor, open source platform 
for observing all aspects of networking. Please read the [collaboration document](./CONTRIBUTING.md) for 
ideas on how you can help. 



