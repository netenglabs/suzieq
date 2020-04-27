# <a name='gathering-data'></a>Gathering Data
Two really important concepts in Suzieq are Nodes and Services. Nodes are devices of some kind;
they are the object being monitored. Services are the data that is collected and consumed by Suzieq. 
Service definitions describe how to get output from devices and then how to turn that into useful data.

Currently Suzieq supports polling [Cumulus Linux](https://cumulusnetworks.com/) or
 [Arista](https://www.arista.com/en/) devices, as well as Linux. 
Suzieq can easily support other device types, we just haven't had access to those and not time to 
chase them down.
Adding new device types starts by created a new [Service](docs/service-file-format.md).
Services do work work for what we have tested, but we have not tested around the edges of how
services are parsed. 
They might just work for you, but if you run into trouble we can only help a little right now. 

Suzieq started out with least common denominator SSH and REST access to devices. 
Suzieq does have support for agents to push data and we've done some experiments with them, but don't
have production versions of that code. 
