## Examples of Pandas Queries

Remember to __use == to do equality check and ensure that all strings are in double quotes__. For example, 
```hostname == "leaf01"```

Parentheses to group checks works and you can use __and__ and __or__ to create a complex condition.

What follows are examples of using Pandas queries in the filter. 

* Filter entries matching a hostname leaf01 (note the use of double-quotes):
    
	```hostname == "leaf01"```

* Filter entries matching multiple hostnames:

    ```hostname == "leaf01" or hostname == "spine01"```

    More efficient: ```hostname == ["leaf01", "spine01"]``` especially as the number of OR entries to match grows.
	
* Filter entries based on regular expression, matching all hostnames starting with spine:

	```hostname.str.contains("spine*")```

* Filter entries based on regular expression, matching interfaces Ethernet1/1-Ethernet1/9

	```ifname.str.contains("1/[1-9]$")``` OR ```ifname.str.contains("1/\d$")```

* Filter entries based on regular expression, matching interfaces Ethernet1/51-Ethernet1/59

	```ifname.str.contains("1/[1-9]$")``` OR ```ifname.str.contains("1/5\d$")```

* Filter entries not matching a hostname:

    ```hostname != "leaf01"```

* Filter entries where MTU is greater than 1500

    ```mtu > 1500```
	
* Filter entries where MTU is between 1500 and 9000

	```1500 < mtu < 9000```
	
* Filter entries with hostname spine01 and interface name Ethernet1/1

	```hostname == "spine01" and ifname == "Ethernet1/1```
	
* Filter entries which are bond members

	```type == "bond_slave"```
	
* Filter routes only if one of the nexthops is Ethernet1/1

	```oifs.str.join(" ").str.contains("Ethernet1/5")```
