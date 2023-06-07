import re
from datetime import datetime
from collections import defaultdict
from json import loads
import numpy as np

from suzieq.poller.worker.services.service import Service
from suzieq.shared.utils import (get_timestamp_from_junos_time,
                                 expand_ios_ifname, expand_nxos_ifname,
                                 convert_macaddr_format_to_colon,
                                 parse_relative_timestamp)
from suzieq.shared.utils import MISSING_SPEED, NO_SPEED, MISSING_SPEED_IF_TYPES


# pylint: disable=too-many-statements

class InterfaceService(Service):
    """Service class for interfaces. Cleanup of data is specific"""

    def __init__(self, name, defn, period, stype, keys, ignore_fields, schema,
                 queue, db_access, run_once="forever"):

        super().__init__(name, defn, period, stype, keys, ignore_fields,
                         schema, queue, db_access, run_once)
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

    def _get_missing_speed_value(self, entry):
        '''
        Return the correct value for an interface without a valid speed
        '''
        if entry.get('type', '') not in MISSING_SPEED_IF_TYPES:
            return NO_SPEED
        return MISSING_SPEED

    def _speed_field_check(self, entry, missing_speed_indicator):
        """
        Return a missing-speed value if the speed is invalid,
        the interface speed otherwise

        MUST be called after the type's been fixed correctly
        """
        if entry.get('speed', missing_speed_indicator) \
           == missing_speed_indicator:
            return self._get_missing_speed_value(entry)
        return entry['speed']

    def _common_speed_field_value(self, entry):
        """Return speed value or a missing value for common retrieved data"""
        return self._speed_field_check(entry, 0)

    def _textfsm_valid_speed_value(self, entry):
        """Return speed value or a missing value for textfsm retrieved data"""
        return self._speed_field_check(entry, '')

    def _clean_eos_data(self, processed_data, _):
        """Clean up EOS interfaces output"""

        entry_dict = defaultdict(dict)
        drop_indices = []
        vlan_entries = {}       # Needed to fix the anycast MAC entries

        # pylint: disable=too-many-nested-blocks
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
                entry['mtu'] = 1500
                entry['speed'] = NO_SPEED
                continue

            if entry['type'] == 'varp':
                for elem, val in vlan_entries.items():
                    ventry = val
                    amac = ventry.get('_anycastMac', '')
                    if amac:
                        ventry['interfaceMac'] = ventry['macaddr']
                        ventry['macaddr'] = amac
                    else:
                        # Found this format in some of the real life deployment
                        amacs = entry.get('_virtualMacs', []) or []
                        for amac in amacs:
                            if amac.get('macType', '') == 'varp':
                                ventry['interfaceMac'] = ventry['macaddr']
                                ventry['macaddr'] = amac['macAddress']
                                break
                drop_indices.append(i)
                continue

            if not entry_dict[entry['ifname']]:
                entry_dict[entry['ifname']] = entry
            elif 'vrf' in entry_dict[entry['ifname']]:
                entry['master'] = entry_dict[entry['ifname']]['vrf']
                entry_dict[entry['ifname']] = entry

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
            entry["lacpBypass"] = (entry["lacpBypass"] is True)
            if entry["forwardingModel"] == "bridged":
                entry["master"] = "bridge"  # Convert it for Linux model
                del entry["forwardingModel"]

            if entry['type']:
                entry['type'] = entry['type'].lower()

            # Vlan is gathered as a list for VXLAN interfaces. Fix that
            if entry["type"] == "vxlan":
                # We capture the glory in evpnVni of this interface
                entry["vlan"] = 0
                entry['mtu'] = -1
                entry['macaddr'] = '00:00:00:00:00:00'

            if entry['type'] == 'vlan' and entry['ifname'].startswith('Vlan'):
                entry['vlan'] = int(entry['ifname'].split('Vlan')[1])
                vlan_entries[entry['ifname']] = entry

            adm_state = entry.get('adminState', 'down')
            if adm_state == 'notconnect':
                entry['reason'] = 'notconnect'
                entry['state'] = 'notConnected'
            elif adm_state == 'errdisabled':
                entry['reason'] = 'errdisabled'
                entry['state'] = 'errDisabled'
            elif adm_state == 'connected':
                entry['adminState'] = 'up'

            speed = self._common_speed_field_value(entry)
            if speed != MISSING_SPEED:
                speed = int(speed / 1000000)
            entry['speed'] = speed

            tmpent = entry.get("ipAddressList", [[]])
            if not tmpent:
                continue

            if entry['type'] == "loopback":
                entry['macaddr'] = '00:00:00:00:00:00'

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
                    ip = elem["address"] + "/" + str(elem["maskLen"])
                    new_list.append(ip)
                if 'virtualIp' in munge_entry:
                    elem = munge_entry['virtualIp']
                    if elem["address"] != "0.0.0.0":
                        ip = f'{elem["address"]}/{str(elem["maskLen"])}'
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

    def _clean_cumulus_data(self, processed_data, _):
        """We have to merge the appropriate outputs of two separate commands"""

        for entry in processed_data:
            if entry.get('hardware', '') == 'ether':
                entry['type'] = 'ethernet'

            if entry['adminState'] == "down":
                entry['state'] = "down"

            if entry['type'] == 'ether':
                entry['type'] = 'ethernet'
            if entry.get('type', '') == 'vxlan':
                entry['speed'] = NO_SPEED

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

            # Lowercase the master value thanks to SoNIC
            entry['master'] = entry.get('master', '').lower()
            if entry['ip6AddressList'] and 'ip6AddressList-_2nd' in entry:
                # This is because textfsm adds peer LLA as well
                entry['ip6AddressList'] = entry['ip6AddressList-_2nd']

            # Remove loopbacks
            entry['ip6AddressList'] = [x for x in entry['ip6AddressList']
                                       if x != "::1/128"]

            if 'type-_2nd' in entry:
                entry['type'] = entry['type-_2nd']

            del entry["linkUpCnt"]
            del entry["linkDownCnt"]
            del entry["linkUpTimestamp"]
            del entry["linkDownTimestamp"]
            del entry["vrf"]

            entry['speed'] = self._textfsm_valid_speed_value(entry)

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        """Cleanup IP addresses and such"""

        def fix_junos_speed(entry):
            speed = str(self._common_speed_field_value(entry))
            if speed.endswith('mbps'):
                speed = int(speed.split('mb')[0])
            elif speed.endswith('Gbps'):
                speed = int(speed.split('Gb')[0])*1000
            elif speed == 'Unlimited':
                speed = self._get_missing_speed_value(entry)
            return speed

        entry_dict = defaultdict(dict)
        drop_indices = []
        new_entries = []

        for i, entry in enumerate(processed_data):

            ifname = entry.get('ifname', '')
            if not entry.get('macaddr', ''):
                entry['macaddr'] = '00:00:00:00:00:00'

            entry['type'] = entry.get('type', '').lower()

            if entry['type'] in ['vrf', 'virtual-router']:
                entry['type'] = 'vrf'
                self._assign_vrf(entry, entry_dict)
                entry['state'] = entry['adminState'] = 'up'
                entry['mtu'] = 1500
                if ifname == 'default':
                    drop_indices.append(i)
                entry['type'] = 'vrf'  # VMX uses virtual-router for VRF
                entry['speed'] = NO_SPEED
                continue

            if entry.get('description', '') == 'None':
                entry['description'] = ''

            if ifname.startswith(('gre', 'ipip', 'lc-', 'lsi', 'pc-', 'bme',
                                  'cbp', 'pimd', 'pime', 'pip', 'pd',
                                  'pd', 'fxp', 'mtun', 'tap', 'bcm', 'jsrv',
                                  'mo-', 'ixgbe')):
                entry['type'] = 'internal'

            if ifname.startswith('irb.'):
                entry['type'] = 'vlan'
            elif ifname == 'irb':
                entry['type'] = 'internal'
            elif ifname == 'dsc':
                entry['type'] = 'null'

            if not entry['type']:
                entry['type'] = 'internal'
                entry['mtu'] = 65536
                entry['speed'] = fix_junos_speed(entry)
                continue

            if entry['type'] == 'virtual-switch':
                # TODO: Handle this properly
                continue

            if entry['type'] == 'vxlan-tunnel-endpoint':
                entry['type'] = 'vtep'

            if entry.get('_minLinksBond', None) is not None:
                entry['type'] = 'bond'

            if entry.get('type', '') == 'vpls':
                entry['state'] = 'up'
                entry['adminState'] = 'up'

            if not entry_dict[ifname]:
                entry_dict[ifname] = entry

            if entry.get('mtu', 0) == 'Unlimited':
                entry['mtu'] = 65536

            entry['mtu'] = int(entry.get('mtu', 0))

            if 'statusChangeTimestamp' in entry:
                ts = get_timestamp_from_junos_time(
                    entry['statusChangeTimestamp'],
                    raw_data[0]['timestamp']/1000)
                entry['statusChangeTimestamp'] = int(ts)

            if entry.get('master', '') == 'Ethernet-Bridge':
                entry['master'] = 'bridge'
            else:
                entry['master'] = ''

            if entry.get('type', '') == 'ethernet-bridge':
                # This is an MX device
                entry['type'] = 'ethernet'
                entry['master'] = 'bridge'

                # extract VLAN
                vlan_tag = entry.get('_vlanTag', [])
                if vlan_tag:
                    words = vlan_tag[0].split('0x8100.')
                    vlan = words[1].split(')')[0]
                else:
                    vlan = 0

                entry['vlan'] = int(vlan)
            entry['speed'] = fix_junos_speed(entry)

            # Process the logical interfaces which are too deep to be parsed
            # efficiently by the parser right now
            for lentry in entry.get('_logIf', []) or []:
                lifname = lentry.get('name', [{}])[0].get('data', '')
                if not lifname:
                    continue
                if '.' in lifname and not lifname.endswith('.0'):
                    _, vlan = lifname.split('.')
                    # This order is important, don't change; irb is an internal
                    # interface
                    if ifname == "irb":
                        iftype = 'vlan'
                    elif entry['type'] == 'internal':
                        iftype = 'internal'
                    else:
                        iftype = 'subinterface'
                    vlan = int(vlan)
                    if vlan > 4095:
                        vlan = 0
                        iftype = 'internal'
                else:
                    vlan = 0
                    iftype = entry['type']

                if iftype == 'subinterface' or lifname.endswith(".0"):
                    speed = lentry \
                        .get('logical-interface-bandwidth', [{}])[0] \
                        .get('data', entry.get('speed', MISSING_SPEED))
                else:
                    speed = lentry \
                        .get('logical-interface-bandwidth', [{}])[0] \
                        .get('data', NO_SPEED)

                if not entry_dict[lifname]:
                    entry_dict[lifname] = {
                        'ifname': lifname,
                        'type': iftype,
                        'vlan': vlan,
                        'speed': speed,
                        'master': ifname,
                        'state': 'up',
                        'adminState': 'up',
                        'mtu': entry.get('mtu', 0),
                        'statusChangeTimestamp':
                        entry.get('statusChangeTimestamp', 0),
                    }

                afis = lentry.get('address-family', []) or []
                no_inet = True
                v4addresses = []
                v6addresses = []
                macaddr = lentry.get('logical-interface-vgw-v4-mac', [{}])[0] \
                    .get('data', '')
                if not macaddr:
                    macaddr = lentry.get('logical-interface-mac', [{}])[0] \
                        .get('data', '')
                if not macaddr:
                    macaddr = entry.get('macaddr', '00:00:00:00:00:00')

                addrlist = []
                afi_mtu = entry['mtu']
                for elem in afis:
                    afi_mtu = elem.get('mtu', [{}])[0].get(
                        'data', entry['mtu'])
                    afi = elem.get('address-family-name', [{}])[0] \
                        .get('data', '')
                    if afi == 'inet':
                        no_inet = False
                        addrlist += elem.get('interface-address', [])
                    elif afi == 'inet6':
                        no_inet = False
                        addrlist += elem.get('interface-address', [])
                    if afi == "aenet":
                        master = elem.get("ae-bundle-name", [{}])[0] \
                            .get("data", "")
                        entry['master'] = master.split('.')[0]
                        entry['type'] = 'bond_slave'
                    if afi in ["eth-switch", "bridge"]:
                        addrlist = []
                        entry['master'] = 'bridge'
                        continue

                if no_inet:
                    continue

                vrf = entry_dict.get(ifname, {}).get('vrf', '')
                l_description = lentry.get('description',
                                           [{}])[0].get('data', '')
                new_entry = {'ifname': lifname,
                             'mtu': afi_mtu,
                             'type': iftype,
                             'speed': speed,
                             'vlan': vlan,
                             'master': vrf,
                             'macaddr': macaddr,
                             'adminState': 'up',
                             'description': l_description,
                             'state': 'up',
                             'statusChangeTimestamp':
                             entry['statusChangeTimestamp'],
                             }

                new_entry['speed'] = fix_junos_speed(new_entry)
                entry_dict[new_entry['ifname']] = new_entry

                flags = lentry.get('if-config-flags',
                                   [{}])[0].get('iff-up', None)
                if flags is not None or (entry.get('type') == 'loopback'):
                    new_entry['state'] = 'up'
                else:
                    new_entry['state'] = 'down'

                if new_entry['mtu'] == 'Unlimited':
                    new_entry['mtu'] = 65536
                else:
                    new_entry['mtu'] = int(new_entry['mtu'])

                for elem in addrlist or []:
                    laddr = elem.get("ifa-local")[0]["data"]
                    if ':' in laddr:
                        plen = (elem.get("ifa-destination",
                                         [{"data": "0/128"}])[0]["data"])
                        if '/' in plen:
                            v6addresses.append(f'{laddr}/{plen.split("/")[1]}')
                        else:
                            v6addresses.append(f'{laddr}/128')
                    else:
                        plen = (elem.get("ifa-destination",
                                         [{"data": "0/32"}])[0]["data"])
                        if '/' in plen:
                            v4addresses.append(f'{laddr}/{plen.split("/")[1]}')
                        else:
                            v4addresses.append(f'{laddr}/32')
                vlanName = lentry.get('irb-domain', [{}])[0] \
                    .get('irb-bridge', [{}])[0] \
                    .get('data', '')
                if not vlanName:
                    new_entry['vlanName'] = vlanName
                else:
                    new_entry['vlanName'] = '-'
                new_entry['ip6AddressList'] = v6addresses
                new_entry['ipAddressList'] = v4addresses

                new_entries.append(new_entry)
            entry.pop('_logIf', [])

        if drop_indices:
            processed_data = np.delete(processed_data, drop_indices).tolist()

        if new_entries:
            processed_data.extend(new_entries)

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):
        """Complex cleanup of NXOS interface data"""

        def fix_nxos_speed(entry):
            speed = str(self._common_speed_field_value(entry))
            if isinstance(speed, str):
                speed = speed.strip()
                if speed.endswith('(D)') or speed.endswith('(I)'):
                    speed = speed[:-3]
                if speed.startswith("unknown enum") or (speed == "auto"):
                    speed = str(self._get_missing_speed_value(entry))
                elif speed.startswith('a-'):
                    speed = speed[2:]

                if speed.endswith('G'):
                    speed = int(speed[:-1])*1000
                elif speed.endswith('Kbit'):
                    speed = int(speed.split()[0])/1000
                elif speed == '--':
                    speed = 0
                else:
                    speed = int(speed or 0)

            return speed

        new_entries = []
        unnum_intf = {}
        drop_indices = []
        entry_dict = {}

        unnum_intf_entry_idx = []  # backtrack to interface to fix

        for entry_idx, entry in enumerate(processed_data):
            if entry.get('_entryType', '') == 'mtumac':
                old_entry_idx = entry_dict.get(entry['ifname'], None)
                if old_entry_idx is not None:
                    old_entry = processed_data[old_entry_idx]
                    admin_state = entry['adminState'].lower()
                    if admin_state:
                        if admin_state == "administratively":
                            admin_state = "down"
                        old_entry['adminState'] = admin_state

                    old_entry['mtu'] = entry.get('mtu', 0) or old_entry['mtu']
                    macaddr = entry.get('macaddr', '')
                    if macaddr and not old_entry.get('_anycastMac', ''):
                        # VLAN MAC addr MUST not be replaced due to fabric SVI
                        old_entry['macaddr'] = convert_macaddr_format_to_colon(
                            macaddr)

                    old_entry['numChanges'] = entry['numChanges'] or 0
                    if entry.get('speed', ''):
                        old_entry['speed'] = fix_nxos_speed(entry)

                    lastChange = entry.get('statusChangeTimestamp', '')
                    if lastChange:
                        if any(x in lastChange for x in 'dwmy'):
                            lastChange = f'{lastChange} hours ago'

                        lastChange = parse_relative_timestamp(
                            lastChange, raw_data[0]['timestamp'], ms=True)
                    if lastChange:
                        old_entry['statusChangeTimestamp'] = lastChange
                    else:
                        old_entry['statusChangeTimestamp'] = 0
                    old_entry['description'] = entry.get('description', '')
                else:
                    self.logger.error(f'{raw_data[0]["hostname"]}: Unable to '
                                      f'find entry for {entry["ifname"]}')
                drop_indices.append(entry_idx)
                continue

            if entry.get('_entryType', '') == "vrf":
                # VRF is not an interface on NXOS, we're doing this to keep
                # it consistent with other NOS. So fill in dummy defaults.
                entry['type'] = 'vrf'
                entry['mtu'] = 1500
                entry['vni'] = 0

            ifname = expand_nxos_ifname(entry['ifname'])
            entry['ifname'] = ifname

            ipaddresses = entry.get('ipAddressList', None)
            pri_ipaddr = ''
            if ipaddresses and ipaddresses != "--":
                pri_ipaddr = f"{entry['ipAddressList']}/{entry['_maskLen']}"
                ipaddr = [pri_ipaddr]
                for i, elem in enumerate(entry.get('_secIPs', [])):
                    if elem:
                        ipaddr.append(f"{elem}/{entry['_secmasklens'][i]}")
                entry['ipAddressList'] = ipaddr
            else:
                entry['ipAddressList'] = []

            if entry.get('ip6AddressList', None):
                if '_linklocal' in entry:
                    entry['ip6AddressList'].append(entry['_linklocal'])
            else:
                entry['ip6AddressList'] = []

            if ifname in entry_dict:
                # Older NXOS has this issue of providing loopback interfaces
                # with shortened names such as Lo0 while the IP addr section
                # lists them with full status such as loopback0. We have to
                # therefore manually merge them
                ifentry = processed_data[entry_dict[ifname]]
                if ifentry.get('type', '') == 'loopback':
                    ifentry['ipAddressList'] = entry['ipAddressList']
                    ifentry['master'] = entry['vrf']
                    ifentry['mtu'] = entry['mtu']
                if entry.get('_child_intf', []):
                    unnum_intf[ifname] = [pri_ipaddr]
                drop_indices.append(entry_idx)
                continue

            entry["statusChangeTimestamp1"] = entry.get(
                "statusChangeTimestamp", '')

            if entry.get('vrf', ''):
                entry['master'] = entry['vrf']

            if 'routeDistinguisher' in entry:
                # This is a VRF entry
                entry['macaddr'] = "00:00:00:00:00:00"
                entry['adminState'] = entry.get("state", "up").lower()
                entry['state'] = entry.get('state', 'down').lower()
                entry['speed'] = 0
                continue

            entry_dict[ifname] = entry_idx

            if 'reason' in entry:
                if entry['reason'] is not None:
                    entry['reason'] = entry['reason'].lower()

                if entry['reason'] == 'none' or not entry['reason']:
                    entry['reason'] = ''

                if entry['reason'] in ["link not connected",
                                       "xcvr not inserted"]:
                    entry['state'] = 'notConnected'

            if entry.get('reason', '') == 'administratively down':
                entry['adminState'] = 'down'
            else:
                entry['adminState'] = 'up'
            portmode = entry.get('_portmode', '')
            if portmode in ['access', 'trunk']:
                entry['master'] = 'bridge'

            portchan = entry.get('_portchannel', 0)
            if portchan and (isinstance(portchan, int) or
                             portchan.isnumeric()):
                entry['master'] = f'port-channel{portchan}'
                entry['type'] = 'bond_slave'

            if ifname.startswith('port-channel'):
                entry['type'] = 'bond'

            if not entry.get('macaddr', ''):
                entry['macaddr'] = "00:00:00:00:00:00"

            if entry.get('_anycastMac', ''):
                entry['interfaceMac'] = entry.get('macaddr', '')
                entry['macaddr'] = entry['_anycastMac']
                if entry.get('_forwardMode', '') != 'Anycast':
                    entry['reason'] += ', Fabric forwarding mode not enabled'

            entry['macaddr'] = convert_macaddr_format_to_colon(
                entry.get('macaddr', '0000.0000.0000'))

            unnum_if_parent = entry.get('_unnum_intf', '')
            if unnum_if_parent:
                if unnum_if_parent in unnum_intf:
                    # IPv6 has link local, so unnumbered is a v4 construct
                    entry['ipAddressList'] = unnum_intf[unnum_if_parent]
                else:
                    unnum_intf_entry_idx.append(entry_idx)

            if entry.get('_child_intf', []):
                unnum_intf[ifname] = [pri_ipaddr]

            if ifname == "mgmt0":
                entry['type'] = "ethernet"

            entry['type'] = entry.get('type', '').lower()
            if entry['type'] == 'eth':
                entry['type'] = 'ethernet'

            if 'ethernet' in entry.get('type', ''):
                entry['type'] = 'ethernet'

            if entry.get('vlan', '') in ["monitor", "--"]:
                entry['vlan'] = 0
            if ifname.startswith('Vlan'):
                entry['type'] = 'vlan'
            elif re.search(r'\.\d+$', ifname):
                entry['type'] = 'subinterface'
            elif ifname.startswith('nve'):
                entry['type'] = 'vxlan'
                entry['master'] = 'bridge'
            elif ifname.startswith('loopback'):
                entry['type'] = 'loopback'
            elif ifname.startswith('tunnel-te'):
                entry['type'] = 'tunnel-te'
            elif ifname.startswith('pw'):
                entry['type'] = 'pseudowire'

            if entry['type'] == 'vlan' and entry['ifname'].startswith('Vlan'):
                entry['vlan'] = int(entry['ifname'].split('Vlan')[1])

            entry['speed'] = fix_nxos_speed(entry)
            # have this at the end to avoid messing up processing

        # Fix unnumbered interface references
        for idx in unnum_intf_entry_idx:
            entry = processed_data[idx]
            entry['ipAddressList'] = unnum_intf.get(entry['_unnum_intf'], [])

        if drop_indices:
            processed_data = np.delete(processed_data, drop_indices).tolist()

        if new_entries:
            processed_data.extend(new_entries)

        return processed_data

    def _clean_linux_data(self, processed_data, _):
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

            entry['speed'] = self._textfsm_valid_speed_value(entry)

            # Linux interface output has no status change timestamp

        return processed_data

    def _clean_iosxr_data(self, processed_data, raw_data):

        entry_dict = {}
        devtype = raw_data[0].get('devtype', 'iosxr')
        drop_indices = []

        for i, entry in enumerate(processed_data):

            if entry.get('_entryType', '') == 'vrf':
                entry['master'] = ''
                entry['type'] = 'vrf'
                entry['mtu'] = -1
                entry['state'] = entry['adminState'] = 'up'
                entry['macaddr'] = "00:00:00:00:00:00"
                entry['speed'] = NO_SPEED
                continue

            if 'type' not in entry:
                # We have some weird outputs when some ephemeral interfaces
                # such as NDE_0 popup between the commands we run causing us
                # to not have full data about this interface. Drop such
                # interfaces. If they're not ephemeral, we'll get them in the
                # next run
                drop_indices.append(i)
                continue

            ifname = entry['ifname']
            if entry.get('_bondMbrs', ''):
                bond_mbrs = ' '.join(entry['_bondMbrs'])
            else:
                bond_mbrs = ''
            state = entry.get('state', '')
            if 'up' in state:
                # IOSVL2 images show up as up (connected)
                entry['state'] = 'up'
            elif 'down' in state:
                if 'notconnect' in state:
                    entry['state'] = 'notConnected'
                elif 'Autostate Enabled' in state:
                    entry['state'] = 'down'
                    entry['reason'] = state.split(',')[1].strip()
                elif 'err-disabled' in state:
                    entry['state'] = 'errDisabled'
                elif 'disabled' in state:
                    entry['state'] = 'down'
                elif 'monitoring' in state:
                    entry['state'] = 'down'
                elif 'suspended' in state:
                    entry['state'] = 'down'
                    if not entry.get('reason', ''):
                        entry['reason'] = 'suspended'

            iftype = entry.get('type', 'ethernet').lower()
            if '.' in entry.get('ifname', ''):
                iftype = 'subinterface'
            elif bond_mbrs or iftype == "etherchannel":
                iftype = 'bond'
            elif iftype in ['ethernet', 'igbe', 'csr']:
                iftype = 'ethernet'
            elif iftype.endswith('gige'):
                iftype = 'ethernet'
            elif iftype.endswith('ge'):
                # Is this safe, assuming just ge ending means GigE?
                iftype = 'ethernet'
            elif iftype.endswith('ethernet'):
                iftype = 'ethernet'
            elif ifname.startswith('tunnel-te'):
                iftype = 'tunnel-te'
            elif ifname.startswith('pw'):
                iftype = 'pseudowire'
            elif ('10ge' in iftype or 'xge' in iftype or
                  'ethernet' in iftype or 'mb 802.3' in iftype or
                  'rp management' in iftype):
                iftype = 'ethernet'
            elif "embedded service engine" in iftype:
                iftype = 'svc-engine'
            elif "async group serial" in iftype:
                iftype = 'async-serial-grp'

            # More iftype processing below before setting it in entry
            speed = self._textfsm_valid_speed_value(entry)
            if speed != MISSING_SPEED:
                speed = int(speed)/1000  # is in Kbps
            entry['speed'] = speed

            if iftype == 'bond' and bond_mbrs:
                for mbr in bond_mbrs.split():
                    mbr = mbr.strip()
                    # expand the member name
                    mbr = expand_ios_ifname(mbr)
                    if mbr in entry_dict:
                        mbr_entry = entry_dict[mbr]
                        mbr_entry['type'] = 'bond_slave'
                        mbr_entry['master'] = entry['ifname']
                    else:
                        entry_dict[mbr] = {'master': entry['ifname'],
                                           'type': 'bond_slave'}

            if entry['adminState'] == 'administratively down':
                entry['adminState'] = 'down'
            else:
                # IOS reports the admin state as down when the oper state
                # (line protocol) is down. administratively down is what
                # is administratively down.
                entry['adminState'] = 'up'

            entry['macaddr'] = convert_macaddr_format_to_colon(
                entry.get('macaddr', '0000.0000.0000'))
            if not entry['macaddr']:
                entry['macaddr'] = '00:00:00:00:00:00'
            if entry['type'] == 'null':
                entry['macaddr'] = "00:00:00:00:00:00"
            entry['interfaceMac'] = convert_macaddr_format_to_colon(
                entry.get('interfaceMac', '0000.0000.0000'))

            lastChange = parse_relative_timestamp(
                entry.get('statusChangeTimestamp', ''),
                raw_data[0]['timestamp'], ms=True)

            if lastChange:
                entry['statusChangeTimestamp'] = lastChange
            if 'ipAddressList' not in entry:
                entry['ipAddressList'] = []
                entry['ip6AddressList'] = []
            elif ':' in entry['ipAddressList']:
                entry['ip6AddressList'] = entry['ipAddressList']
                entry['ipAddressList'] = []
            elif devtype == 'iosxr':
                entry['ip6AddressList'] = []

            if entry['ifname'].startswith('Vlan'):
                iftype = 'vlan'
                if entry.get('vlan', '') == '':
                    entry['vlan'] = entry['ifname'].split('Vlan')[1].strip()
            if entry.get('vlan', '') and entry.get('innerVlan', ''):
                iftype = "qinq"

            entry['type'] = iftype
            # This is specifically for IOSXE/IOS devices where
            # the IPv6 address uses capital letters
            if devtype != 'iosxr':
                entry['ip6AddressList'] = [x.lower()
                                           for x in entry.get('ip6AddressList',
                                                              [])]

            if entry['ifname'].endswith('.0'):
                entry['vlan'] = 0
            elif entry.get('vlan', '') == '':
                if entry['ipAddressList'] == entry['ip6AddressList'] == []:
                    entry['vlan'] = 1

            if entry['ipAddressList'] == 'Unknown':
                entry['ipAddressList'] = []
                entry['ip6AddressList'] = []

            if entry['ipAddressList'] or entry['ip6AddressList']:
                entry['master'] = entry.get('vrf', '')

            if entry['ifname'] in entry_dict:
                add_info = entry_dict[entry['ifname']]
                entry['master'] = add_info.get('master', '')
                entry['type'] = add_info.get('type', '')
            else:
                entry_dict[entry['ifname']] = entry

        if drop_indices:
            processed_data = np.delete(processed_data, drop_indices).tolist()

        return processed_data

    def _clean_iosxe_data(self, processed_data, raw_data):
        return self._clean_iosxr_data(processed_data, raw_data)

    def _clean_ios_data(self, processed_data, raw_data):
        return self._clean_iosxr_data(processed_data, raw_data)

    def _clean_sonic_data(self, processed_data, raw_data):
        return self._clean_cumulus_data(processed_data, raw_data)

    def _common_data_cleaner(self, processed_data, _):
        for entry in processed_data:
            entry['state'] = entry['state'].lower()

        return processed_data

    def _clean_panos_data(self, processed_data, _):
        mtu_data = {}
        interfaces = {}
        for entry in processed_data:
            _mtu_data = entry.get("_mtu_data")
            iftype = entry.get("type")
            master = entry.get("master")
            speed = entry.get("speed")
            state = entry.get("state")
            ipAddressList = entry.get("ipAddressList", [])
            ip6AddressList = entry.get("ip6AddressList", [])
            _ip = entry.get("_ip", "")

            # mtu values are collected separatly
            if _mtu_data:
                # fix json so that it can be parsed
                d = _mtu_data.split(": ", 1)[1].replace("'", "\"")
                d = re.sub(
                    r"([a-fA-F0-9]{2}(:[a-fA-F0-9]{2}){5})", r'"\1"', d)
                d = re.sub(r"(\"[\w0-9\.\/]+\": \{\s\},\s)", r"", d)
                d = re.sub(r"(,\s\})", r" }", d)
                j = loads(d)
                for ifname, value in j.items():
                    mtu_data[ifname] = value["mtu"]
                continue

            if entry["ifname"] in mtu_data:
                entry["mtu"] = mtu_data[entry["ifname"]]
            else:
                entry["mtu"] = ""

            # only hw if specify type value
            if iftype:
                if iftype == '0':
                    entry["type"] = "ethernet"
                elif iftype == '3':
                    entry["type"] = "vlan"
                elif iftype == '5':
                    entry["type"] = "loopback"
                elif iftype == '6':
                    entry["type"] = "tunnel"
                else:
                    # not sure if it's better to put unknown
                    entry["type"] = ""

            if master:
                if master != "N/A":
                    entry["master"] = master.split(":")[1]
                else:
                    entry["master"] = "default"

            # speed is not always provided
            if speed and speed == "[n/a]":
                # if it is a physical interface, it's not good
                if entry["type"] == "ethernet":
                    entry["speed"] = MISSING_SPEED
                else:
                    entry["speed"] = NO_SPEED

            # this happens when there's only one entry
            if isinstance(ipAddressList, str):
                entry["ipAddressList"] = [ipAddressList]

            if isinstance(ip6AddressList, str):
                entry["ip6AddressList"] = [ip6AddressList]

            if _ip and _ip != "N/A" and _ip != "unknown":
                if ":" in _ip:
                    entry["ip6AddressList"] = entry.get("ip6AddressList", []) \
                        + [_ip]
                else:
                    entry["ipAddressList"] = entry.get("ipAddressList", []) \
                        + [_ip]
            if state and "/" in state:
                # clear from [n/a] before splitting
                entry['state'] = state.replace("[n/a]", "").split("/")[2]

            if "management" in entry["ifname"].lower():
                entry["state"] = "up"
                entry["type"] = "ethernet"

            if entry.get("type") == "ethernet":
                # physical interface, save data to use with subinterfaces
                interfaces[entry["ifname"]] = {}
                interfaces[entry["ifname"]]["mtu"] = entry["mtu"]
                interfaces[entry["ifname"]]["speed"] = entry["speed"]
                interfaces[entry["ifname"]]["state"] = entry["state"]
                interfaces[entry["ifname"]]["adminState"] = entry["adminState"]

            if "." in entry["ifname"]:
                parentIf, _ = entry["ifname"].split(".")
                if parentIf in interfaces:
                    entry["mtu"] = interfaces[parentIf]["mtu"]
                    entry["state"] = interfaces[parentIf]["state"]
                    entry["adminState"] = interfaces[parentIf]["adminState"]
                    entry["speed"] = interfaces[parentIf]["speed"]
                    entry["type"] = "subinterface"

        # remove mtu data cmd
        if len(processed_data) > 1:
            processed_data.pop(0)
        return processed_data
