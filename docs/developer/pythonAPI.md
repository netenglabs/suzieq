# Python API

Suzieq provides a simple, consistent Python API for those who wish to interact with Suzieq via Python. It hews very much to the REST API which in turn hews close enough to the CLI. If you know how to type in the CLI for an operation, its pretty close to what you can do with the Python API. 

Suzieq organizes information into tables. The main steps in using the Python API is:

* Get a handle to a table
* Use this handle to perform one of several operations (expressed as **verbs**) providing some options to filter the data. 
* Suzieq then returns the result as a Pandas DataFrame

You can choose to do further operations on the Pandas DataFrame.

Lets look at each of the steps described above in a little more detail.

## Obtaining a Sqobject Handle

The first step in using the Python API is to get the handle to a table object that you can then request some action on. `get_sqobject()` is the API call to get a handle to a table. You pass a single variable to the call, the name of the table you want to access. The python fragment to access the OSPF table is:

```
from suzieq.sqobjects import get_sqobject

ospf_tbl = get_sqobject('ospf')
```

## Table Operations

Each table suppoets a set of verbs as functions to operate on the table. All tables support the **get**, **summary** and **unique** methods. Some of the objects support the aver method (for checking the correctness of a bunch of parameters. If you invoke an unsupported function on a table, you get back a DataFrame with an error that indicates that the operation is not supported on the table. 

The invocation of the method follows the format of ```<table>(table_params).<verb>(verb params)```. For example, invoking the get method on the OSPF table in its simplest form looks like this:
```
ospf_df = ospf_tbl().get()
```

Two common table parameters that can be passed are:

* The start and end time windows (start_time, end_time)
* The config file to be used (config_file). This is used to specify the location of the database as well as parameters such as the timezone to be used. If you don't specify a config file, Suzieq looks for a file first in `./suzieq-cfg.yml` and if it's not found there, then in `~/.suzieq/suzieq-cfg.yml`.

The common verb parameters are:

* *namespace:* The list of namespaces to select the data from. By default, it means select from all known namespaces in the DB
* *hostname:* The list of hostnames you're specifically selecting to view the data from. By default, it means select all hostnames in the selected namespace(s).
* *view:* to decide if you want to see just the latest data (the default) or all the data (view='all'). If you have a lot of data, 'all' can take a very long time.
* *columns:* The list of columns you want to returned in response or you want to operate on (for unique, top). You can use ['*'] to mean all columns. By default, there is a default set of columns defined for each table. When used with unique, the default column is always hostname.

Besides these, the get and unique methods take an additional parameter:

* *query_str:* Which is the Panndas query string to filter out the data returned

Every table takes an additional set of keywords specific to the table. For example, you can use ifname keyword to the interfaces table or LLDP table to request the operation only on the list of interfaces specified; you can use protocol as a keyword to the routing table to select only those routing table entries populated by the specified protocol, and so on.
 
