import numpy as np

from suzieq.poller.services.service import Service
import ipaddress


class OspfIfService(Service):
    """OSPF Interface service. Output needs to be munged"""

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["vrf"] = "default"
            entry["networkType"] = entry["networkType"].lower()
            if entry['networkType'] == 'point2point':
                entry['networkType'] = 'p2p'
            entry["passive"] = entry["passive"] == "Passive"
            entry["isUnnumbered"] = entry["isUnnumbered"] == "UNNUMBERED"

        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_eos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["networkType"] = entry["networkType"].lower()
            entry["isUnnumbered"] = False
            # Rewrite '/' in interface names

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
            entry['ipAddress'] = ipaddress.IPv4Interface(
                f'{entry["ipAddress"]}/{entry["maskLen"]}').with_prefixlen
            entry['maskLen'] = int(entry['ipAddress'].split('/')[1])
            entry['vrf'] = 'default'  # Juniper doesn't provide this info
            entry['authType'] = entry['authType'].lower()

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
                for j, area in enumerate(entry['ifname']):
                    for ifentry in areas.get(area, []):
                        ifentry['routerId'] = entry['routerId']
                        ifentry['authType'] = entry['authType'][j]
                        ifentry['isBackbone'] = area == "0.0.0.0"
                drop_indices.append(i)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data
