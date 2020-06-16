from suzieq.poller.services.service import Service
import ipaddress


class OspfIfService(Service):
    """OSPF Interface service. Output needs to be munged"""

    def clean_data(self, processed_data, raw_data):

        dev_type = self._get_devtype_from_input(raw_data)
        if dev_type == "cumulus" or dev_type == "linux":
            processed_data = self._clean_cumulus_data(processed_data, raw_data)
        elif dev_type == "eos":
            processed_data = self._clean_eos_data(processed_data, raw_data)
        elif dev_type == "junos":
            processed_data = self._clean_junos_data(processed_data, raw_data)
        elif dev_type == "nxos":
            processed_data = self._clean_nxos_data(processed_data, raw_data)

        return super().clean_data(processed_data, raw_data)

    def _clean_cumulus_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["vrf"] = "default"
            entry["networkType"] = entry["networkType"].lower()
            if entry['networkType'] == 'point2point':
                entry['networkType'] = 'p2p'
            entry["passive"] = entry["passive"] == "Passive"
            entry["isUnnumbered"] = entry["isUnnumbered"] == "UNNUMBERED"
            entry['origIfname'] = entry['ifname']

        return processed_data

    def _clean_eos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["networkType"] = entry["networkType"].lower()
            entry["isUnnumbered"] = False
            entry['origIfname'] = entry['ifname']
            # Rewrite '/' in interface names
            entry['ifname'] = entry['ifname'].replace('/', '-')

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry['passive'] = entry['passive'] == "Passive"
            if entry['networkType'] == "LAN":
                entry['networkType'] = "broadcast"
            entry['stub'] = not entry['stub'] == 'Not Stub'
            entry['ipAddress'] = ipaddress.IPv4Interface(
                f'{entry["ipAddress"]}/{entry["maskLen"]}').with_prefixlen
            entry['maskLen'] = int(entry['ipAddress'].split('/')[1])
            entry['vrf'] = 'default'  # Juniper doesn't provide this info
            entry['authType'] = entry['authType'].lower()

            # Rewrite '/' in interface names
            entry['ifname'] = entry['ifname'].replace('/', '-')

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):
        areas = {}              # Need to come back to fixup entries

        for entry in processed_data:
            if entry['_entryType'] == 'interfaces':
                entry['ifname'] = entry['ifname'].replace('/', '-')
                entry["networkType"] = entry["networkType"].lower()
                if entry['networkType'] == "loopback":
                    entry['passive'] = True
                    entry['ipAddress'] = f"{entry['ipAddress']}/{entry['maskLen']}"
                if entry['area'] not in areas:
                    areas[entry['area']] = []

                areas[entry['area']].append(entry)
            else:
                # ifname is really the area name
                for i, area in enumerate(entry['ifname']):
                    for ifentry in areas.get(area, []):
                        ifentry['routerId'] = entry['routerId']
                        ifentry['authType'] = entry['authType'][i]
                        ifentry['isBackbone'] = entry['isBackbone'][i] == "true"

        return processed_data
