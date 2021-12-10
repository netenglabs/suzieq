# Source
A source plugin has the duty to load devices from a source.

Every source plugin must inherit from `.base_source.Source` and override
the following functions:
- `_validate_config(input_data)`: validates the input data received by the contructor
- `_load(input_data)`: load the content of input data into the source object

**Attention**: Do not directly assign the variable `self.inventory` inside a source. Every source MUST call the `set_inventory()` function to do so;
if this function is not called, `get_inventory()` will never succeed.poller

## SqNativeFile(Default)
Loads devices from the native Suzieq inventory format
```yaml
- namespace: eos  # devices namespace
  type: file      # source type (optional)
  hosts:          # list of devices
    - url: https://vagrant@192.168.123.252 devtype=eos
    - url: ssh://vagrant@192.168.123.232  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/internet/libvirt/private_key
    - url: ssh://192.168.123.70 username=admin password=admin
    - url: ssh://vagrant@192.168.123.54:2023  keyfile=/home/netenglabs/cloud-native-data-center-networking/topologies/dual-attach/.vagrant/machines/server104/libvirt/private_key
    - url: https://vagrant@192.168.123.123 password=vagrant
```

## AnsibleInventory
Loads devices from the ansible format.
The format of the ansible file must be generated using `ansible-inventory --list` command.
```yaml
- namespace: ansible                        # devices namespace
  type: ansible                             # source type
  file_path: /home/netenglabs/ansible.json  # ansible file path
```
## Netbox
Loads devices from netbox using REST APIs.

Netbox doesn't provide by its own a method to collect device credentials.
For this reason in the inventory file must be also specified the method used to retrieve these informations.

**Attention**: the transport method provided into the inventory file will be set to all devices.
In the current version there is no way to define a distinct trasport method for each device
```yaml
- namespace: "testing"                                  # devices namespace
  type: netbox                                          # source type
                                                        # that it must connect to netbox

  token: "af8717c89ec0ff420c19d89e6c20646ad05dd54e"     # REST token
  url: "http://127.0.0.1:8000"                          # netbox host
  transport: ssh                                        # devices transport protocol (optional)
                                                        # Default: 'ssh'

  tag: "suzieq-demo"                                    # tag to search in netbox (optional)
                                                        # Default: 'suzieq'

  device_credentials:                                   # contains the method to retrieve devices credentials
    type: <credential_loader_type>                      # credential loader type
    # credential loader parameters


```
