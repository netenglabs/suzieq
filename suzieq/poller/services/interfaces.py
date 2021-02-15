from datetime import datetime
from collections import defaultdict

import numpy as np
from suzieq.poller.services.service import Service
from suzieq.utils import get_timestamp_from_junos_time
from suzieq.utils import convert_macaddr_format_to_colon


class InterfaceService(Service):
    """Service class for interfaces. Cleanup of data is specific"""

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, run_once="forever"):

        super().__init__(name, defn, period, stype, keys, ignore_fields,
                         schema, queue, run_once)
        # Thanks to JunOS obsolete timestamp, we cannot use the
        # statusChangeTimestamp field directly. We use an artificial field
        # called statusChangeTimestamp1 to ensure we capture changes
        self.ignore_fields.append("statusChangeTimestamp")

    def _assign_vrf(self, entry, entry_dict):
        '''Uses the interface List to assign interfaces to VRFs'''
        if entry['type'] == 'vrf':
            if entry['ifname'] != 'default':
                for intf in entry['_interfaceList']:
                    if intf in entry_dict:
                        entry_dict[intf]['master'] = entry['ifname']
                    else:
                        entry_dict[intf] = {'vrf': entry['ifname']}

    def _clean_eos_data(self, processed_data, raw_data):
        """Clean up EOS interfaces output"""

        entry_dict = defaultdict(dict)
        drop_indices = []
        vlan_entries = {}       # Needed to fix the anycast MAC entries

        for i, entry in enumerate(processed_data):

            if entry['type'] == 'vrf':
                if entry['ifname'] == 'default':
                    drop_indices.append(i)
                    continue

                self._assign_vrf(entry, entry_dict)
                entry['macaddr'] = '00:00:00:00:00:00'
                entry['master'] = ''
                entry['state'] = 'up'
                entry['adminState'] = 'up'
                continue

            if entry['type'] == 'varp':
                for elem in vlan_entries:
                    ventry = vlan_entries[elem]
                    ventry['interfaceMac'] = ventry['macaddr']
                    ventry['macaddr'] = entry['_anycastMac']
                drop_indices.append(i)
                continue

            if not entry_dict[entry['ifname']]:
                entry_dict[entry['ifname']] = entry
            elif 'vrf' in entry_dict[entry['ifname']]:
                entry['master'] = entry_dict[entry['ifname']]['vrf']
                entry_dict[entry['ifname']] = entry

            entry["speed"] = int(entry["speed"] / 1000000)
            ts = entry["statusChangeTimestamp"]
            if ts:
                entry["statusChangeTimestamp"] = int(float(ts) * 1000)
            else:
                entry["statusChangeTimestamp"] = 0
            # artificial field for comparison with previous poll result
            entry["statusChangeTimestamp1"] = entry.get(
                "statusChangeTimestamp", '')
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
                vlan_entries[entry['ifname']] = entry

            if entry.get('adminState', 'disabled') != 'disabled':
                entry['adminState'] = 'up'

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
                        ip = f'{elem["address"]}/{elem["maskLen"]}'
                        new_list.append(ip)
                entry["ipAddressList"] = new_list

            # ip6AddressList is formatted as a dict, not a list by EOS
            munge_entry = entry.get("ip6AddressList", [{}])
            if munge_entry:
                new_list = []
                for elem in munge_entry.get("globalUnicastIp6s", []):
                    new_list.append(elem["subnet"])
                entry["ip6AddressList"] = new_list

        if drop_indices:
            processed_data = np.delete(processed_data, drop_indices).tolist()

        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        """We have to merge the appropriate outputs of two separate commands"""
        new_data_dict = {}
        for entry in processed_data:
            ifname = entry["ifname"]
            if entry.get('hardware', '') == 'ether':
                entry['type'] = 'ethernet'

            if entry['adminState'] == "down":
                entry['state'] = "down"

            if entry['type'] == 'ether':
                entry['type'] = 'ethernet'
            if ifname not in new_data_dict:

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
                # artificial field for comparison with previous poll result
                entry["statusChangeTimestamp1"] = entry.get(
                    "statusChangeTimestamp", '')

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

        entry_dict = defaultdict(dict)
        drop_indices = []
        new_entries = []

        for i, entry in enumerate(processed_data):

            if entry['type'] == 'vrf':
                self._assign_vrf(entry, entry_dict)
                if entry['ifname'] == 'default':
                    drop_indices.append(i)
                continue

            if entry['type'] is None:
                continue

            if entry['type'] == 'virtual-switch':
                # TODO: Handle this properly
                continue

            if not entry_dict[entry['ifname']]:
                entry_dict[entry['ifname']] = entry

            if entry.get('mtu', 0) == 'Unlimited':
                entry['mtu'] = 65536

            entry['mtu'] = int(entry.get('mtu', 0))

            if entry['type']:
                entry['type'] = entry['type'].lower()

            if 'statusChangeTimestamp' in entry:
                ts = get_timestamp_from_junos_time(
                    entry['statusChangeTimestamp'], raw_data[0]['timestamp']/1000)
                entry['statusChangeTimestamp'] = int(ts)

            if entry.get('speed', ''):
                if entry['speed'].endswith('mbps'):
                    entry['speed'] = int(entry['speed'].split('mb')[0])
                elif entry['speed'].endswith('Gbps'):
                    entry['speed'] = int(entry['speed'].split('Gb')[0])*1000
                elif entry['speed'] == 'Unlimited':
                    entry['speed'] = 0

            if entry['master'] == 'Ethernet-Bridge':
                entry['master'] = 'bridge'
            elif entry['master'] == 'unknown':
                if entry['ifname'].startswith('jsv'):
                    entry['type'] = 'sflowMonitor'
                else:
                    entry['type'] = 'virtual'
                entry['master'] = ''
            else:
                entry['master'] = ''

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
            gwmacs = entry.get('_gwMacaddr', [])
            for i, ifname in enumerate(entry['logicalIfname']):
                v4addresses = []
                v6addresses = []
                macaddr = None
                if len(gwmacs) > i:
                    macaddr = gwmacs[i]
                if not macaddr:
                    macaddr = entry.get('macaddr', '')

                if entry['afi'][i] is None:
                    continue
                for x in entry['afi'][i]:
                    if isinstance(x, list):
                        afi = x[0].get('interface-address', None)
                    else:
                        afi = x.get('interface-address', None)
                    if afi and afi is not None:
                        break
                    foo = x.get('address-family-name', None)
                    if foo and (foo[0].get('data', None) == "eth-switch"):
                        afi = []
                        break
                else:
                    continue

                if entry_dict[ifname]:
                    vrf = entry_dict[ifname]['vrf']
                else:
                    vrf = ''
                new_entry = {'ifname': ifname,
                             'mtu': entry['afi'][i][0].get(
                                 'mtu', [{'data': 0}])[0]['data'],
                             'type': 'logical',
                             'speed': entry['speed'],
                             'master': vrf,
                             'macaddr': macaddr,
                             'adminState': 'up',
                             'description': entry['description'],
                             'statusChangeTimestamp':
                             entry['statusChangeTimestamp'],
                             }
                new_entries.append(new_entry)
                entry_dict[new_entry['ifname']] = new_entry
                if (entry['logicalIfflags'][i][0].get('iff-up') or
                        entry.get('type') == 'loopback'):
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

            entry.pop('vlanName')

        if drop_indices:
            processed_data = np.delete(processed_data, drop_indices).tolist()

        if new_entries:
            processed_data.extend(new_entries)

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):
        """Complex cleanup of NXOS interface data"""
        new_entries = []
        unnum_intf = {}
        drop_indices = []
        entry_dict = defaultdict(dict)

        unnum_intf_entry_idx = []  # backtrack to interface to fix

        for entry_idx, entry in enumerate(processed_data):
            # if its the Linux ip link command output, massage the ifname
            # and copy over the values and drop the entry_dict
            if entry.get('_entryType', '') == 'mtumac':
                old_entry = entry_dict[entry['ifname']]
                if old_entry:
                    old_entry['mtu'] = entry.get('mtu', 0)
                    old_entry['macaddr'] = convert_macaddr_format_to_colon(
                        entry.get('macaddr', '0000.0000.0000'))
                    if old_entry.get('_portchannel'):
                        pc_entry = entry_dict.get(old_entry['master'], None)
                        if pc_entry:
                            # The later ethernet port entries' MAC addr wins
                            # over the earlier ones
                            pc_entry['mtu'] = entry.get('mtu', 0)
                            pc_entry['macaddr'] = entry['macaddr']
                drop_indices.append(entry_idx)
                continue

            entry_dict[entry['ifname']] = entry

            # artificial field for comparison with previous poll result
            entry["statusChangeTimestamp1"] = entry.get(
                "statusChangeTimestamp", '')

            entry['state'] = entry.get('state', 'unknown').lower()
            if entry.get('vrf', 'default') != 'default':
                entry['master'] = entry['vrf']
            else:
                entry['master'] = ''

            if 'routeDistinguisher' in entry:
                entry['macaddr'] = "00:00:00:00:00:00"
                entry['adminState'] = entry.get("state", "up").lower()
                continue

            if 'reason' in entry:
                if entry['reason'] == '"Administratively down':
                    entry['adminState'] = 'down'
                else:
                    entry['adminState'] = 'up'

                if entry['reason'] is not None:
                    entry['reason'] = entry['reason'].lower()

                if entry['reason'] == 'none' or not entry['reason']:
                    entry['reason'] = ''

            portmode = entry.get('_portmode', '')
            if portmode == 'access' or portmode == 'trunk':
                entry['master'] = 'bridge'

            portchan = entry.get('_portchannel', '')
            if portchan:
                entry['master'] = f'port-channel{portchan}'
                entry['type'] = 'bond_slave'

            if entry['ifname'].startswith('port-channel'):
                entry['type'] = 'bond'

            if 'ipAddressList' in entry:
                pri_ipaddr = f"{entry['ipAddressList']}/{entry['_maskLen']}"
                ipaddr = [pri_ipaddr]
                for i, elem in enumerate(entry.get('_secIPs', [])):
                    if elem:
                        ipaddr.append(f"{elem}/{entry['_secmasklens'][i]}")
                entry['ipAddressList'] = ipaddr
            else:
                entry['ipAddressList'] = []

            if 'ip6AddressList' in entry:
                if '_linklocal' in entry:
                    entry['ip6AddressList'].append(entry['_linklocal'])
            else:
                entry['ip6AddressList'] = []

            if entry.get('_anycastMac', ''):
                entry['interfaceMac'] = entry.get('macaddr', '')
                entry['macaddr'] = entry['_anycastMac']
                if entry.get('_forwardMode', '') != 'Anycast':
                    entry['reason'] += ', Fabric forwarding mode not enabled'

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
            if isinstance(speed, str):
                if speed.startswith("unknown enum"):
                    entry['speed'] = 0
                elif speed.startswith('a-'):
                    entry['speed'] = int(speed[2:])

            entry['type'] = entry.get('type', '').lower()
            if entry['type'] == 'eth':
                entry['type'] = 'ethernet'

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

        # Fix unnumbered interface references
        for idx in unnum_intf_entry_idx:
            entry = processed_data[idx]
            entry['ipAddressList'] = unnum_intf.get(entry['ifname'], [])

        if drop_indices:
            processed_data = np.delete(processed_data, drop_indices).tolist()

        if new_entries:
            processed_data.extend(new_entries)

        return processed_data

    def _clean_linux_data(self, processed_data, raw_data):
        """Pluck admin state from flags"""
        for entry in processed_data:
            if entry['type'] == 'ether':
                entry['type'] = 'ethernet'
            entry['state'] = entry['state'].lower()
            if entry['state'] == 'unknown':
                entry['state'] = 'up'  # loopback
            if ',UP' in entry['_flags']:
                entry['adminState'] = 'up'
            else:
                entry['adminState'] = 'down'

            # Linux interface output has no status change timestamp

        return processed_data

    def _common_data_cleaner(self, processed_data, raw_data):
        for entry in processed_data:
            entry['state'] = entry['state'].lower()

        return processed_data
