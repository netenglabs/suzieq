'''
Parsing Configuration utilities
'''
from typing import Dict
from ciscoconfparse import CiscoConfParse


def get_access_port_interfaces(conf: CiscoConfParse,
                               nos: str) -> Dict[str, int]:
    '''For various NOS return the list of access port interfaces.

    This module uses the CiscoConfParse to extract the interface names.
    '''
    if 'junos' in nos:
        ifmap = _get_swport_interfaces_junos(conf, what='access')
    elif 'cumulus' in nos:
        ifmap = _get_swport_interfaces_cls(conf, what='access')
    else:
        ifmap = _get_swport_interfaces_iosy(conf, what='access')

    return ifmap


def get_trunk_port_interfaces(conf: CiscoConfParse,
                              nos: str) -> Dict[str, int]:
    '''For various NOS return the list of access port interfaces.

    This module uses the CiscoConfParse to extract the interface names.
    '''
    if 'junos' in nos:
        ifmap = _get_swport_interfaces_junos(conf, what='trunk')
    elif 'cumulus' in nos:
        ifmap = _get_swport_interfaces_cls(conf, what='trunk')
    else:
        ifmap = _get_swport_interfaces_iosy(conf, what='trunk')

    return ifmap


# Do not invoke these functions directly, the implementation can change
def _get_swport_interfaces_junos(conf: CiscoConfParse,
                                 what: str) -> Dict[str, int]:
    '''Return interfaces that match the requested info for Junos.

    This involves parsing the Junos config looking for the relevant info.
    what can be access or trunk. For access ports, we return a Dict[str, int]
    of interfaces that are access ports with the value that is the access vlan.
    '''

    pm_dict = {}
    if conf.syntax != 'junos':
        raise ValueError('Invalid config passed for Junos')

    if what == 'access':
        block = conf.find_objects_w_all_children('', ['interface-mode access'],
                                                 recurse=True)
        # The format returned is 3 lines for each interface with the first
        # line being the interface name
        for index in range(1, len(block), 3):
            ifname = block[index].text.strip()
            vlan_ln = [line for line in block[index].lineage
                       if 'members' in line.text]
            if vlan_ln:
                vlan = vlan_ln[0].text.split('members')[1].strip()
                if vlan.isnumeric():
                    pm_dict[ifname] = int(vlan)
                else:
                    vlan = 0

    return pm_dict


def _get_swport_interfaces_cls(conf: CiscoConfParse,
                               what: str) -> Dict[str, int]:
    '''Return interfaces that match the requested info for Cumulus.

    This involves parsing the ifupdown2 config looking for the relevant info.
    what can be access or trunk. For access ports, we return a dict that
    contains the access vlan for the interface.
    '''
    pm_dict = {}
    if what == 'access':
        for intf in conf.find_objects_w_all_children(
                '^iface ', ['bridge-access']):
            ifname = intf.text.split('iface')[1].strip()
            acc_vlan = intf.re_match_iter_typed(r'^.*bridge-access\s+(\d+)')
            if acc_vlan.isnumeric():
                pm_dict[ifname] = int(acc_vlan)
            else:
                pm_dict[ifname] = 0
    if what == "trunk":
        acc_ports = []
        for intf in conf.find_objects_w_all_children(
                '^iface ', ['bridge-access']):
            acc_ports.append(intf.text.split('iface')[1].strip())

        bridge_port_lines = conf.find_lines('bridge-ports')
        for line in bridge_port_lines:
            if line.strip().startswith('#'):
                continue
            # This line looks like this:
            # bridge-ports bond01 bond02 peerlink vni13 vni24 vxlan4001
            # Ignore the keyword, and trunk ports are those that are not
            # access ports
            brports = line.split()[1:]
            pm_dict = {port: '1' for port in brports
                       if port not in acc_ports}

        # Now we need to find the PVID for the ports
        for intf in conf.find_objects_w_child('iface ', 'bridge-pvid'):
            port = intf.text.split('iface')[1].strip()
            if port not in pm_dict:
                vlan = intf.re_match_iter_typed(r'bridge-pvid\s+(\d+)')
            else:
                vlan = intf.re_match_iter_typed(r'bridge-pvid\s+(\d+)')
            if vlan.isnumeric():
                pm_dict['port'] = int(vlan)
            else:
                pm_dict['port'] = 0
    return pm_dict


def _get_swport_interfaces_iosy(conf: CiscoConfParse,
                                what: str) -> Dict[str, int]:
    '''Return interfaces that match the requested info for IOSy NOS.

    This involves parsing the config looking for the relevant info. This is
    for devices which use an IOS-like config such as EOS, NXOS, IOSXR etc.
    what can be access or trunk. For access ports, we return a dict that
    contains the access vlan for the interface.
    '''

    pm_dict = {}
    if what == 'access':
        for intf in conf.find_objects_w_child(r'^interface ',
                                              r'^\s+switchport.*access'):
            ifname = intf.text.split('interface')[1].strip()
            acc_vlan = intf.re_match_iter_typed(r'^.*vlan\s+(\d+)')
            if acc_vlan.isnumeric():
                pm_dict[ifname] = int(acc_vlan)
            else:
                pm_dict[ifname] = 0

    if what == 'trunk':
        for intf in conf.find_objects_w_child(r'^interface',
                                              r'^\s+switchport.*trunk'):
            ifname = intf.text.split('interface')[1].strip()
            nvlan = intf.re_match_iter_typed(r'.*native vlan\s+(\d+)',
                                             default='1')
            if nvlan.isnumeric():
                pm_dict[ifname] = int(nvlan)
            else:
                pm_dict[ifname] = 0

    return pm_dict
