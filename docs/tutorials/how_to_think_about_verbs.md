## How to reason about your network with Suzieq verbs

As we've mentioned in our [Introduction](index.html), the Suzieq cli has commands, verbs and 
filters. We are going to talk about the verbs in this doc.

Almost every command has three common verbs: show, summarize, and unique. Another set of common
verbs are top and assert. Some commands have other verbs specific to them as well.



### show
Show is the most basic verb. Every command has a show verb. It will return the
most basic data for that command. Often there is a direct mapping from a service
to a command, and the show command will show data from that table.

The show verb, like the others, allows filtering. For show, the columns filter
is especially useful.

Some examples

![bgp show](../images/suzieq-bgp-show.png)

Path show looks some different in that you have to provide more arguments for it to work. Path
displays the path between two endpoints so it requires a src and dest.
![path show](../images/suzieq-path-show.png)

Table show looks a bit differernt than the other commands, because table show is showing 
the tables in the database, not directly looking at data inside tables.
![table show](../images/suzieq-table-show.png) 

Some of the tables have a lot of columns. We have a standard set of default columns for
each table. However, you can add a columns= filter to add more columns or see less. columns=*
shows all the columns.

Some examples of columns with filters
![bgp show with filters]()


### summarize
Summarize works through the data and 

![path summarize]()
### unique
unique does not work on the path command.

### asssert
assert works on bgp, interface, ospf, and  


### top
top works on interface, device 


### lpm
lpm only works on the route command


### describe
describe only works for the table command

