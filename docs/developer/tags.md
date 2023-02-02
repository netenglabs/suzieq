# Tags for SuzieQ and Mfn

__NOTE WELL: THESE ARE IDEAS OF WHAT WE WANT TO DO WITH SUZIEQ, NOTHING OUTSIDE OF NAMESPACE is SUPPORTED YET__

Both SuzieQ and Mfn need to be able to have these tags to group things together and they should be the same groups.

When we first think of tags, we think of device tags, but really lots of things need tags. We will want to be able to group interfaces as well. Maybe there are other attributes that need tags.

## Devices

Device tags are the most important. I think what we want is two different dimensions: namespace and role.

Use cases:

* all tor devices in every datacenter
* all wan devices in evey branch office
* all switches in west cost branch offices
* all transit routers in New York datacenters

### Namespace

* each device is in a single namespace
* namespaces can be grouped together
* the easiest way is by regex, but could also list them out
* namespaces can be in many groups
* build a hierarchy of namespaces: groups of groups

### Device Role

* devices can be in many roles
* roles can be in multiple role_groups

 describe here, then have a script that edits suzieq config based on this?
  I think this is the only trick part of the problem, how do we go from this simple setup to using it?

 I want to be able to filter by namespace (or namespace_group) and by role (or role_group)

### description

we want to be able to use regex and we want them to be based on the tag, so to desribe these relationships will look like:

``` YAML
namespaces:
   junos: ['vqfx*', 'srv*']

namespace_group:
   new_york: ['junos', 'fooey']
   east_cost_us : ['new_york', 'virginia']

device_roles:
   leaf:
   spine:
   core:
   edge:
   srv:

device_role_group:
   datacenter: ['leaf', 'spine', 'core', 'edge']
# or the ansible way
device_roles:
   datacenter:
      children: ['leaf', 'spine', 'core', 'edge']
```

### how to use the data

scripts needed

* a library and command line sript that will take a device name and return the namespace, namespace_groups, roles and role_groups
* read ansible config files and creates our data file if you already have ansible groups
* something that combines hosts with tags and produces various files

### for MfN

for MfN it needs tags at the time of recording the data

* read ansible inventory, and our tags database, and produce the telegraf file necessary for SNMP (and other metrics) for each host -- something like suzieq genhosts for MfN/telegraf
* what If I don't have ansible
** create a hosts file, and then have a script that reads that hostfile and updates the groups? 

### Dynamic description for SuzieQ

For SuzieQ, we want to get the tags at analysis time, rather than at write time, so suzieq-cli will need to use the above library to read the database. (why did I say this, doesn't it need to be recorded over time just like MfN?)

### Questions

* do we need to store how roles are related to each other?
* how do we get different tags related to different hosts for telegraf/MfN?
* do we want to have role_group, or be more like ansible and just describe children.
* we need to represent operational state like: inservice, OOS, provisioning, decommission. Are these just role tags?
* even for suzieq, we'll probably want to know what groups something was when it was recorded won't we

## Interface roles

We will have to also describe interfaces for some important interfaces. For instance, I want to group all my transit interfaces, or all my verizon interfaces, etc.

Not sure how to do that yet.
