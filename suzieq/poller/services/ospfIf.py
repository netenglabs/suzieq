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
        elif dev_type == "junos":
            for entry in processed_data:
                entry['passive'] = entry['passive'] == "Passive"
                if entry['networkType'] == "LAN":
                    entry['networkType'] = "broadcast"
                entry['stub'] = not entry['stub'] == 'Not Stub'
                entry['ipAddress'] = ipaddress.IPv4Interface(
                    f'{entry["ipAddress"]}/{entry["maskLen"]}').with_prefixlen
                for i in ['cost', 'deadTime', 'helloTime', 'retxTime',
                          'nbrCount']:
                    entry[i] = int(entry[i])
                entry['maskLen'] = int(entry['ipAddress'].split('/')[1])
                entry['vrf'] = 'default'  # Juniper doesn't provide this info

                # Rewrite '/' in interface names
                entry['ifname'] = entry['ifname'].replace('/', '-')

        return super().clean_data(processed_data, raw_data)
