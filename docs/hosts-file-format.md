# Hosts File #

The list of hosts for suzieq to pull information from is specified via the hosts file, supplied as an input parameter to starting suzieq. The list is in YAML with the following structure:

``` json
- namespace: <name of the namespace this list of hosts correspinds to>
  hosts:
	  - url: <url-of-host-1> [device=eos|nxos|linux|cumulus|jnpr|ios]
	  - url: <url-of-host-2> [device=eos|nxos|linux|cumulus|jnpr|ios]
	  ...
```

The url specification has to be in one of the following formats:
``<ssh|https|http|local>://[username:[password]@]<ip-addr-or-dns-hostname>[:port]``

A sample hosts file looks as follows:
``` json
- namespace: test
  hosts:
       - url: ssh://vagrant@192.168.122.20
       - url: https://vagrant@192.168.122.150 device=eos
       - url: ssh://vagrant@192.168.122.37
       - url: ssh://vagrant@127.0.0.1:2000
```
The hostname specified must either be an IP address or a hostname resolvable via DNS.  **Do not use TABS in the file**.

The device type is important to identify the command selection for a given service. 

It is required to specify the device type when using REST API to query the information from the device because the REST 
API of each device is different, and it is not possible to automatically identify that. 

In case of using SSH to query
the device state, suzeiq runs the commands 'show version and hostnamectl' to try, and identify the device. Most 
networking gear support the 'show version' model and all open networking products I'm aware of and servers support 
hostnamectl. Using these two commands, we can identify the type of device. If you're running a device that does not 
support either of these commands, specify it using the **device** parameter.


## Local Agent ##

It is possible to run Suzieq in a push model where the code runs as a local agent pushing information via a mechanism such as [Kafka](https://kafka.apache.org/). 

In such a situation, the **local** URL specification is used to launch the command as a local command instead of SSH. The device type identification is also done using the same model as for SSH.

## Password Specification ##

The recommended model for passwords is to use a public key for the running user 'suzieq' to allow passwordless access to the device. If this is not done, then a separate read-only file containing the password for each user can be provided. This latter method is not as secure and is discouraged. For users testing with vagrant, if the user name is vagrant, a default password of vagrant is assumed.
