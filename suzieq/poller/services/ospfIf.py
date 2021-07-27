import numpy as np

from suzieq.poller.services.service import Service
from ipaddress import ip_address, IPv4Interface


class OspfIfService(Service):
    """OSPF Interface service. Output needs to be munged"""

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["vrf"] = "default"
            entry["networkType"] = entry["networkType"].lower()
            if entry['networkType'] == 'pointopoint':
                entry['networkType'] = 'p2p'
            entry["passive"] = entry["passive"] == "Passive"
            entry["isUnnumbered"] = entry["isUnnumbered"] == "UNNUMBERED"

        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_eos_data(self, processed_data, raw_data):

        vrf_loip = {}
        vrf_rtrid = {}
        drop_indices = []
        for i, entry in enumerate(processed_data):
            if '_entryType' in entry:
                # Retrieve the VRF and routerID
                vrf_rtrid[entry.get('vrf', 'default')] = \
                    entry.get('routerId', '')
                drop_indices.append(i)
                continue

            vrf = entry.get('vrf', '')
            if entry['ifname'].startswith("Loopback"):
                if vrf not in vrf_loip or not vrf_loip[vrf]:
                    vrf_loip[vrf] = entry.get('ipAddress', '')
            if entry.get('passive', False):
                entry['bfdStatus'] = "invalid"
            entry["networkType"] = entry["networkType"].lower()
            entry["isUnnumbered"] = False
            if entry.get('state', '') in ['dr', 'p2p']:
                entry['state'] = 'up'

        for i, entry in enumerate(processed_data):
            if entry.get('ipAddress', '') == vrf_loip.get(
                    entry.get('vrf', ''), ''):
                if not entry.get('type', '') == "loopback":
                    entry['isUnnumbered'] = True
            if entry['vrf'] in vrf_rtrid:
                entry['routerId'] = vrf_rtrid[entry['vrf']]

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):

        for entry in processed_data:
            if entry['_entryType'] == 'overview':
                routerId = entry['routerId']
                continue

            entry['routerId'] = routerId
            # Is this right? Don't have a down interface example
            entry['state'] = 'up'
            entry['passive'] = entry['passive'] == "Passive"
            if entry['networkType'] == "LAN":
                entry['networkType'] = "broadcast"
            entry['stub'] = not entry['stub'] == 'Not Stub'
            entry['ipAddress'] = IPv4Interface(
                f'{entry["ipAddress"]}/{entry["maskLen"]}').with_prefixlen
            entry['maskLen'] = int(entry['ipAddress'].split('/')[1])
            entry['vrf'] = 'default'  # Juniper doesn't provide this info
            entry['authType'] = entry['authType'].lower()
            entry['networkType'] = entry['networkType'].lower()

        # Skip the original record as we don't need the overview record
        return processed_data[1:]

    def _clean_nxos_data(self, processed_data, raw_data):
        areas = {}              # Need to come back to fixup entries
        drop_indices = []

        for i, entry in enumerate(processed_data):
            if entry['_entryType'] == 'interfaces':
                entry["networkType"] = entry["networkType"].lower()
                if entry['ifname'].startswith('loopback'):
                    entry['passive'] = True
                entry['ipAddress'] = \
                    f"{entry['ipAddress']}/{entry['maskLen']}"
                if entry['area'] not in areas:
                    areas[entry['area']] = []

                if entry.get('_adminState', '') == "down":
                    entry['state'] = "adminDown"

                areas[entry['area']].append(entry)
            else:
                # ifname is really the area name
                if not entry.get('ifname', []):
                    drop_indices.append(i)
                    continue

                for j, area in enumerate(entry['ifname']):
                    for ifentry in areas.get(area, []):
                        ifentry['routerId'] = entry['routerId']
                        ifentry['authType'] = entry['authType'][j]
                        ifentry['isBackbone'] = area == "0.0.0.0"
                drop_indices.append(i)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_ios_data(self, processed_data, raw_data):
        for entry in processed_data:
            area = entry.get('area', '')
            if area and area.isdecimal():
                entry['area'] = str(ip_address(int(area)))
            entry["networkType"] = entry["networkType"].lower()
            entry["passive"] = entry["passive"] == "stub"
            entry["isUnnumbered"] = entry["isUnnumbered"] == "yes"
            entry['areaStub'] = entry['areaStub'] == "yes"
            entry['helloTime'] = int(
                entry['helloTime']) if entry['helloTime'] else 10  # def value
            entry['deadTime'] = int(
                entry['deadTime']) if entry['deadTime'] else 40  # def value
            entry['retxTime'] = int(
                entry['retxTime']) if entry['retxTime'] else 5  # def value
            entry['vrf'] = 'default'  # IOS doesn't provide this info
            entry['authType'] = entry.get('authType', '').lower()
            entry['nbrCount'] = int(
                entry['nbrCount']) if entry['nbrCount'] else 0
            entry['noSummary'] = entry.get('noSummary', False)
            if entry['state'] == "administratively down":
                entry['state'] = "down"
            else:
                entry['state'] = entry['state'].lower()

        return processed_data

    def _clean_iosxe_data(self, processed_data, raw_data):
        return self._clean_ios_data(processed_data, raw_data)
