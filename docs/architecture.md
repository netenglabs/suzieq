#TBD

## Overview

At this point, Suzieq has two main processes: the poller (sq-poller), and the client (suzieq-cli). The poller is long running and writes data to parquet files. The client doesn't communicate with the poller, it just directly reads the data from parquet. 

## Relationships

* service <-> table
* command <-> tables
* poller service <-> node
* sqobject <-> command

## Poller

### Service

### Node

## Engine


## SqObjects


## SqCommands