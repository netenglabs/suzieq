from suzieq.poller.services.service import Service
import ipaddress


class OspfIfService(Service):
    """OSPF Interface service. Output needs to be munged"""

    def clean_data(self, processed_data, raw_data):

        dev_type = raw_data.get("devtype", None)
        if dev_type == "cumulus" or dev_type == "linux":
            for entry in processed_data:
                entry["vrf"] = "default"
                entry["networkType"] = entry["networkType"].lower()
                entry["passive"] = entry["passive"] == "Passive"
                entry["isUnnumbered"] = entry["isUnnumbered"] == "UNNUMBERED"
                entry["areaStub"] = entry["areaStub"] == "[Stub]"
        elif dev_type == "eos":
            for entry in processed_data:
                entry["networkType"] = entry["networkType"].lower()
                entry["isUnnumbered"] = False
                entry['origIfname'] = entry['ifname']
                # Rewrite '/' in interface names
                entry['ifname'] = entry['ifname'].replace('/', '-')
        elif dev_type == "junos":
            for entry in processed_data:
                entry['passive'] = entry['passive'] == "Passive"
                if entry['networkType'] == "LAN":
                    entry['networkType'] = "broadcast"
                entry['stub'] = not entry['stub'] == 'Not Stub'
                entry['ipAddress'] = ipaddress.IPv4Interface(
                    f'{entry["ipAddress"]}/{entry["maskLen"]}').with_prefixlen
                entry['maskLen'] = int(entry['ipAddress'].split('/')[1])
                entry['vrf'] = 'default'  # Juniper doesn't provide this info

                # Rewrite '/' in interface names
                entry['ifname'] = entry['ifname'].replace('/', '-')
        elif dev_type == "nxos":
            for entry in processed_data:
                # Rewrite '/' in interface names
                entry['ifname'] = entry['ifname'].replace('/', '-')
                entry["networkType"] = entry["networkType"].lower()
                if entry['networkType'] == "loopback":
                    entry['passive'] = True
                entry['ipAddress'] = f"{entry['ipAddress']}/{entry['maskLen']}"

        return super().clean_data(processed_data, raw_data)
