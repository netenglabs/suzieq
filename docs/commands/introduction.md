Commands are the basis of interacting with data in SuzieQ.
The format of each SuzieQ CLI command is the following `<command> <verb> <filters>`.<br>
To get a stripped down description of the commands, there is the `help` command directly inside the CLI.
# Commands
Each SuzieQ service collects specific informations from the devices and collect them inside a table.
Each command access one or more of these tables and prompt devices data to the user.
The list of commands currently supported is the following:

 - arpnd
 - bgp
 - device
 - evpnVni
 - fs
 - interface
 - lldp
 - mac
 - mlag
 - ospf
 - path
 - route
 - sqpoller
 - table
 - topology (alpha)
 - vlan

# Verbs
For each one of the commands above there are the following verbs:

- `describe`: gives a description of the table associated with the command and its fields
- `help`: prints an help message for the command
- `show`: prints the data relative to the table associated with the command
- `summarize`: produce a summarization of the data inside the table
- `top`: find the top n values for a field specified with the `what` argument. This argument is mandatory
- `unique`: find the list of unique items associated with a column specified with `columns` argument.

To get the list of command verbs, it's possible to type `help <command>` or `<command> help`.
## Command specific verbs
bgp, evpnVni, interface and ospf contains a specific verb called `assert` which will run predefined set of assertions on these tables.
For further details about predefined assertions [click here](../analyzer.md#asserts).

network command offers a unique verb `find`. It can be used to find a either an IP or a mac address inside the dataset using the argument `address`
(f.e. `network find address='10.0.0.21'`).

the `show` verb of path command needs `namespace`, `src` and `dest` arguments in order to return the path between `src` and `dest`.
# Filters
Filters can be used to visualize a subset of the network.
There are a set of filters which are common and others which are specific to some commands and/or verbs.
The common filters are the following:

- `columns`: space separeted list of table columns to show.
- `end_time`: all the data polled are associated with a timestamp. It's possible to get the status of the network until end_time timestamp.
- `engine`: select the engine for the command. The supported engines are `pandas` and `rest`
- `format`: select the output format. The supported formats are `text`(default), `json`, `csv` and `markdown`.
- `hostname`: filter a subset of hostnames. Multiple hostnames can be specified separating them with a blank.
  It's also possible to filter using a regex adding a `~` at the beginning of the filter (f.e. `bgp show hostname='~spine.*'`)
- `namespace`: filter a subset of the namespaces. As hostname, it's possible to specify multiple space separated namespaces and `~` for regex.
- `query_str`: use a pandas query to create a complex query on data. Check [Pandas Query Examples](../pandas-query-examples.md) section for more details about pandas queries.
- `start_time`: similarly to `end_time`, also this command is used to get the status of the network starting from `start_time` timestamp.
- `view`: this filter is used to decide whether showing the state of the network (`view=latest`(default)) or the changes happened (`view=all`)

To get verbs filters, it's possible to use the command `help <command> <verb>`.
