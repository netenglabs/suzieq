## Panos support - alpha feature

Palo Alto firewalls support is currently an alpha feature. This means that some workarounds are needed to let Suzieq poll these devices. We tested it with a PA-VM with PanOS version 8.0 but should be compatible with higher versions too.

At the moment Suzieq cannot discover automatically if a node is running panos, therefore this should be manually specified in the inventory. If you haven't checked out the new inventory format for Suzieq, read the [related docs](./inventory.md) before proceeding.

If you are using Netbox or Ansible as source, Suzieq cannot pull the device type information from it. Therefore, you will need to define another source only for the panos device in order to specify the devtype. For example:

```yaml
sources:
  # only non-panos devices in this source
  - name: vagrant
    type: ansible
    path: /path/to/ansible/list.json
    # works with netbox too
    # type: netbox
    # url: https://netbox.instance
  - name: panos
    type: ansible
    path: /path/to/ansible/panos-list.json
devices:
  - name: all
    ignore-known-hosts: true
    # this will copy the default values from 'all' and override the
    # 'devtype' to panos
  - name: panos
    devtype: panos
    copy: all
namespaces:
  - name: vagrant
    source: vagrant
    device: all
    # having the same name, a single namespace will be created that will be 
    # the result of the merge of the two groups
  - name: vagrant
    source: panos
    device: panos
```

Otherwise, if the panos device is specified in a host list, then all you need to do is add `devtype=panos`:

```yaml
sources:
  - name: my-list
    hosts:
    - url: https://vagrant@10.255.2.7 devtype=panos
    - url: ssh://vagrant@10.0.0.1:22 keyfile=/path/to/private_key
    - url: ssh://vagrant@10.0.0.2:22 devtype=eos keyfile=/path/to/private_key
devices:
  - name: all
    ignore-known-hosts: true
namespaces:
  - name: dc-edge-01
    source: my-list
    device: all
```

The services currently supported are:

- device
- interfaces
- routes
- lldp
- arpnd
- bgp