from datetime import datetime
from suzieq.poller.services.service import Service


class InterfaceService(Service):
    """Service class for interfaces. Cleanup of data is specific"""

    def clean_eos_data(self, processed_data):
        """Clean up EOS interfaces output"""
        for entry in processed_data:
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
                entry["ipAddressList"] = new_list

            # ip6AddressList is formatted as a dict, not a list by EOS
            munge_entry = entry.get("ip6AddressList", [{}])
            if munge_entry:
                new_list = []
                for elem in munge_entry.get("globalUnicastIp6s", []):
                    new_list.append(elem["subnet"])
                entry["ip6AddressList"] = new_list

    def clean_cumulus_data(self, processed_data):
        """We have to merge the appropriate outputs of two separate commands"""
        new_data_dict = {}
        for entry in processed_data:
            ifname = entry["ifname"]
            if entry.get('hardware', '') == 'ether':
                entry['hardware'] = 'ethernet'
            if ifname not in new_data_dict:

                if not entry['linkUpCnt']:
                    entry['linkUpCnt'] = 0
                if not entry['linkDownCnt']:
                    entry['linkDownCnt'] = 0

                entry["numChanges"] = int(entry["linkUpCnt"] +
                                          entry["linkDownCnt"])
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

    def clean_data(self, processed_data, raw_data):
        """Homogenize the IP addresses across different implementations
        Input:
            - list of processed output entries
            - raw unprocessed data
        Output:
            - processed output entries cleaned up
        """
        devtype = raw_data.get("devtype", None)
        if devtype == "eos":
            self.clean_eos_data(processed_data)
        elif devtype == "cumulus" or devtype == "platina":
            processed_data = self.clean_cumulus_data(processed_data)
        else:
            for entry in processed_data:
                entry['state'] = entry['state'].lower()

        return super().clean_data(processed_data, raw_data)
