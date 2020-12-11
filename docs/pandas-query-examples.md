## Examples of Pandas Queries

Remember to __use == to do equality check and ensure that all strings are in double quotes__. For example, 
```hostname == "leaf01"```

Parentheses to group checks works and you can use __and__ and __or__ to create a complex condition. __Not__ is a little more interesting. Look at the examples to see this.

What follows are examples of using Pandas queries in the filter. 

* Filter entries matching a hostname leaf01 (note the use of double-quotes)
&nbsp;&nbsp;&nbsp;&nbsp; hostname == "leaf01"

* Filter entries matching multiple hostnames
&nbsp;&nbsp;&nbsp;&nbsp; hostname == "leaf01" or hostname == "spine01"
&nbsp;&nbsp;&nbsp;&nbsp; Alternate: hostname.str.contains("leaf01|spine01")

* Filter entries not matching a hostname
&nbsp;&nbsp;&nbsp;&nbsp;hostname != "leaf01"

* 
