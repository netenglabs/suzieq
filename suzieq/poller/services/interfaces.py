import re
from datetime import datetime
from suzieq.poller.services.service import Service
from suzieq.utils import get_timestamp_from_junos_time
from suzieq.utils import convert_macaddr_format_to_colon


class InterfaceService(Service):
    """Service class for interfaces. Cleanup of data is specific"""

    def _clean_eos_data(self, processed_data, raw_data):
        """Clean up EOS interfaces output"""

        for entry in processed_data:
            entry['origIfname'] = entry['ifname']
            entry["speed"] = int(entry["speed"] / 1000000)
            ts = entry["statusChangeTimestamp"]
            if ts:
                entry["statusChangeTimestamp"] = int(float(ts) * 1000)
            else:
                entry["statusChangeTimestamp"] = 0
            if entry["type"] == "portChannel":
                entry["type"] = "bond"
            words = entry.get("master", "")
            if words:
                words = words.split()
                if words[-1].strip().startswith("Port-Channel"):
                    entry["type"] = "bond_slave"
                entry["master"] = words[-1].strip()
            entry["lacpBypass"] = (entry["lacpBypass"] == True)
            if entry["forwardingModel"] == "bridged":
                entry["master"] = "bridge"  # Convert it for Linux model
                del entry["forwardingModel"]

            # Vlan is gathered as a list for VXLAN interfaces. Fix that
            if entry["type"] == "vxlan":
                entry["vlan"] = entry.get("vlan", [""])[0]

            if entry['type']:
                entry['type'] = entry['type'].lower()

            if entry['type'] == 'vlan' and entry['ifname'].startswith('Vlan'):
                entry['vlan'] = int(entry['ifname'].split('Vlan')[1])

            tmpent = entry.get("ipAddressList", [[]])
            if not tmpent:
                continue

            munge_entry = tmpent[0]
            if munge_entry:
                new_list = []
                primary_ip = (
                    munge_entry["primaryIp"]["address"]
                    + "/"
                    + str(munge_entry["primaryIp"]["maskLen"])
                )
                new_list.append(primary_ip)
                for elem in munge_entry["secondaryIpsOrderedList"]:
                    ip = elem["adddress"] + "/" + elem["maskLen"]
                    new_list.append(ip)
                if 'virtualIp' in munge_entry:
                    elem = munge_entry['virtualIp']
                    if elem["address"] != "0.0.0.0":
                        ip = elem["adddress"] + "/" + elem["maskLen"]
                        new_list.append(ip)
                entry["ipAddressList"] = new_list

            # ip6AddressList is formatted as a dict, not a list by EOS
            munge_entry = entry.get("ip6AddressList", [{}])
            if munge_entry:
                new_list = []
                for elem in munge_entry.get("globalUnicastIp6s", []):
                    new_list.append(elem["subnet"])
                entry["ip6AddressList"] = new_list

        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        """We have to merge the appropriate outputs of two separate commands"""
        new_data_dict = {}
        for entry in processed_data:
            ifname = entry["ifname"]
            if entry.get('hardware', '') == 'ether':
                entry['type'] = 'ethernet'

            if entry['type'] == 'ether':
                entry['type'] = 'ethernet'
            if ifname not in new_data_dict:

                entry['origIfname'] = entry['ifname']
                if not entry['linkUpCnt']:
                    entry['linkUpCnt'] = 0
                if not entry['linkDownCnt']:
                    entry['linkDownCnt'] = 0

                entry["numChanges"] = (int(entry["linkUpCnt"]) +
                                       int(entry["linkDownCnt"]))
                entry['state'] = entry['state'].lower()
                if entry["state"] == "up":
                    ts = entry["linkUpTimestamp"]
                else:
                    ts = entry["linkDownTimestamp"]
                if "never" in ts or not ts:
                    ts = 0
                else:
                    ts = int(
                        datetime.strptime(
                            ts.strip(), "%Y/%m/%d %H:%M:%S.%f"
                        ).timestamp()
                        * 1000
                    )
                entry["statusChangeTimestamp"] = ts

                if '(' in entry['master']:
                    entry['master'] = entry['master'].replace(
                        '(', '').replace(')', '')

                if entry['ip6AddressList'] and 'ip6AddressList-_2nd' in entry:
                    # This is because textfsm adds peer LLA as well
                    entry['ip6AddressList'] = entry['ip6AddressList-_2nd']

                del entry["linkUpCnt"]
                del entry["linkDownCnt"]
                del entry["linkUpTimestamp"]
                del entry["linkDownTimestamp"]
                del entry["vrf"]
                new_data_dict[ifname] = entry
            else:
                # Merge the two. The second entry is always from ip addr show
                # And it has the more accurate type, master list
                first_entry = new_data_dict[ifname]
                first_entry.update({"type": entry["type"]})
                first_entry.update({"master": entry["master"]})

        processed_data = []
        for _, v in new_data_dict.items():
            processed_data.append(v)

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        """Cleanup IP addresses and such"""
        new_entries = []        # Add new interface entries for logical ifs
        for entry in processed_data:

            if entry['mtu'] == 'Unlimited':
                entry['mtu'] = 65536
            else:
                entry['mtu'] = int(entry['mtu'])

            if entry['type']:
                entry['type'] = entry['type'].lower()

            if (entry['statusChangeTimestamp'] == 'Never' or
                    entry['statusChangeTimestamp'] is None):
                entry['statusChangeTimestamp'] = 0
            else:
                ts_str = re.match(r'.*\((.+) ago\)$',
                                  entry['statusChangeTimestamp'])
                ts = get_timestamp_from_junos_time(
                    ts_str.group(1), raw_data[0]['timestamp']/1000)
                entry['statusChangeTimestamp'] = int(ts)

            if entry['speed']:
                if entry['speed'].endswith('mbps'):
                    entry['speed'] = int(entry['speed'].split('mb')[0])
                elif entry['speed'].endswith('Gbps'):
                    entry['speed'] = int(entry['speed'].split('Gb')[0])*1000
                elif entry['speed'] == 'Unlimited':
                    entry['speed'] = 0

            entry['ifname'] = entry['ifname'].replace('/', '-')

            if entry['master'] == 'Ethernet-Bridge':
                entry['master'] = 'bridge'
            elif entry['master'] == 'unknown':
                if entry['ifname'].startswith('jsv'):
                    entry['type'] = 'sflowMonitor'
                else:
                    entry['type'] = 'virtual'
                entry['master'] = None
            else:
                entry['master'] = None

            if entry['type'] == 'vxlan-tunnel-endpoint':
                entry['type'] = 'vtep'
            elif entry['type'] == 'interface-specific':
                entry['type'] = 'tap'

            # Process the logical interfaces which are too deep to be parsed
            # efficiently by the parser right now
            if entry['logicalIfname'] == [] or entry['afi'] == [None]:
                entry.pop('logicalIfname')
                entry.pop('afi')
                entry.pop('vlanName')
                continue

            # Uninteresting logical interface
            for i, ifname in enumerate(entry['logicalIfname']):
                v4addresses = []
                v6addresses = []
                if entry['afi'][i] is None:
                    continue
                for x in entry['afi'][i]:
                    if isinstance(x, list):
                        afi = x[0].get('interface-address', None)
                    else:
                        afi = x.get('interface-address', None)
                    if afi and afi is not None:
                        break
                else:
                    continue

                new_entry = {'ifname': ifname,
                             'origIfname': ifname,
                             'mtu': entry['afi'][i][0].get(
                                 'mtu', [{'data': 0}])[0]['data'],
                             'type': 'logical',
                             'speed': entry['speed'],
                             'master': entry['ifname'],
                             'description': entry['description'],
                             'statusChangeTimestamp':
                             entry['statusChangeTimestamp'],
                             }
                if entry['logicalIfflags'][i][0].get('iff-up'):
                    new_entry['state'] = 'up'
                else:
                    new_entry['state'] = 'down'

                if new_entry['mtu'] == 'Unlimited':
                    new_entry['mtu'] = 65536
                else:
                    new_entry['mtu'] = int(new_entry['mtu'])

                for x in afi:
                    address = (x.get("ifa-local")[0]["data"] + '/' +
                               x.get("ifa-destination", [{"data": "0/32"}])[0]
                               ["data"].split("/")[1])
                    if ':' in address:
                        v6addresses.append(address)
                    else:
                        v4addresses.append(address)
                vlanName = entry['vlanName'][i]
                if vlanName is not None:
                    new_entry['vlanName'] = vlanName
                else:
                    new_entry['vlanName'] = '-'
                new_entry['ip6AddressList'] = v6addresses
                new_entry['ipAddressList'] = v4addresses

                new_entry['ifname'] = new_entry['ifname'].replace('/', '-')
                new_entries.append(new_entry)

            entry.pop('vlanName')

        if new_entries:
            processed_data.extend(new_entries)
        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):
        """Complex cleanup of NXOS interface data"""
        new_entries = []
        created_if_list = set()
        unnum_intf = {}
        add_bridge_intf = False
        bridge_intf_state = "down"
        bridge_mtu = 1500

        unnum_intf_entry_idx = []  # backtrack to interface to fix

        for entry_idx, entry in enumerate(processed_data):
            entry['origIfname'] = entry['ifname']
            if entry['type'] == 'eth':
                entry['type'] = 'ethernet'

            if ('vrf' in entry and entry['vrf'] != 'default' and
                    entry['vrf'] not in created_if_list):
                # Our normalized behavior is to treat VRF as an interface
                # NXOS doesn't do that. So, create a dummy interface
                new_entry = {'ifname': entry['vrf'],
                             'mtu': 65536,
                             'state': 'up',
                             'type': 'vrf',
                             'master': '',
                             'vlan': 0}
                new_entries.append(new_entry)
                created_if_list.add(entry['vrf'])

                entry['master'] = entry['vrf']
            else:
                entry['master'] = ''

            if entry['_portmode'] == 'access' or entry['_portmode'] == 'trunk':
                entry['master'] = 'bridge'
                add_bridge_intf = True
                if entry['state'] == "up":
                    bridge_intf_state = "up"
                if entry.get('mtu', 1500) < bridge_mtu:
                    bridge_mtu = entry.get('mtu', 0)

            if 'ipAddressList' in entry:
                pri_ipaddr = f"{entry['ipAddressList']}/{entry['_maskLen']}"
                ipaddr = [pri_ipaddr]
                for i, elem in enumerate(entry.get('_secIPs', [])):
                    if elem:
                        ipaddr.append(f"{elem}/{entry['_secmasklens'][i]}")
                entry['ipAddressList'] = ipaddr

            if 'ip6AddressList' in entry:
                if '_linklocal' in entry:
                    entry['ip6AddressList'].append(entry['_linklocal'])

            entry['macaddr'] = convert_macaddr_format_to_colon(
                entry.get('macaddr', '0000.0000.0000'))

            if entry.get('_unnum_intf', ''):
                if entry['ifname'] in unnum_intf:
                    # IPv6 has link local, so unnumbered is a v4 construct
                    entry['ipAddressList'] = [unnum_intf[entry['ifname']]]
                else:
                    unnum_intf_entry_idx.append(entry_idx)

            for elem in entry.get('_child_intf', []):
                unnum_intf[elem] = [pri_ipaddr]

            speed = entry.get('speed', '')
            if isinstance(speed, str) and speed.startswith("unknown enum"):
                entry['speed'] = 0

            entry['type'] = entry['type'].lower()
            if entry['ifname'].startswith('Vlan'):
                entry['type'] = 'vlan'
            elif entry['ifname'].startswith('nve'):
                entry['type'] = 'vxlan'
                entry['master'] = 'bridge'
            elif entry['ifname'].startswith('loopback'):
                entry['type'] = 'loopback'

            if entry['type'] == 'vlan' and entry['ifname'].startswith('Vlan'):
                entry['vlan'] = int(entry['ifname'].split('Vlan')[1])

            # have this at the end to avoid messing up processing
            entry['ifname'] = entry['ifname'].replace('/', '-')

        # Fix unnumbered interface references
        for idx in unnum_intf_entry_idx:
            entry = processed_data[idx]
            entry['ipAddressList'] = unnum_intf.get(entry['origIfname'], [])

        # Add bridge interface
        if add_bridge_intf:
            new_entry = {'ifname': 'bridge',
                         'mtu': bridge_mtu,
                         'state': bridge_intf_state,
                         'type': 'bridge',
                         'master': '',
                         'vlan': 0}
            new_entries.append(new_entry)

        if new_entries:
            processed_data.extend(new_entries)

        return processed_data

    def _clean_linux_data(self, processed_data, raw_data):
        """Pluck admin state from flags"""
        for entry in processed_data:
            entry['state'] = entry['state'].lower()
            if entry['state'] == 'unknown':
                entry['state'] = 'up'  # loopback
            if ',UP' in entry['_flags']:
                entry['adminState'] = 'up'
            else:
                entry['adminState'] = 'down'
            entry['origIfname'] = entry['ifname']

        return processed_data

    def _common_data_cleaner(self, processed_data, raw_data):
        for entry in processed_data:
            entry['state'] = entry['state'].lower()

        return processed_data
