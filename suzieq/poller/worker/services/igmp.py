import json

from suzieq.poller.worker.services.service import Service
from suzieq.shared.utils import (
    get_timestamp_from_cisco_time,
    parse_relative_timestamp
)


class IgmpService(Service):
    """Igmp Service."""

    def _clean_eos_data(self, _, raw_data):
        processed_data = []
        pre_processed_data = {}
        # get date for parsing up time
        cmd_timestamp = raw_data[0].get("cmd_timestamp")
        for data in raw_data:
            if "vrf" in data.get("cmd"):
                cmd = data["cmd"].split()
                vrf = cmd[cmd.index("vrf") + 1]
            else:
                vrf = "default"
            if vrf not in pre_processed_data:
                pre_processed_data.update({vrf: {}})
            if isinstance(data["data"], str):
                json_data = json.loads(data.get("data"))
            else:
                json_data = None
            if json_data:
                # dynamic group "show ip igmp groups" cmd output
                if "groupList" in json_data:
                    for entry in json_data["groupList"]:
                        processed_data.append(
                            {
                                "group": entry["groupAddress"],
                                "interface": entry["interfaceName"],
                                "lastUpTime": parse_relative_timestamp(
                                    str(entry["uptime"]), cmd_timestamp / 1000
                                ),
                                "vrf": vrf,
                                "flag": "dynamic",
                            }
                        )
                # static group "show ip igmp static-groups" cmd output
                if "intfAddrs" in json_data:
                    for interface in json_data["intfAddrs"]:
                        for group in json_data["intfAddrs"][interface][
                            "groupAddrsList"
                        ]:
                            processed_data.append(
                                {
                                    "group": group["groupAddr"],
                                    "interface": interface,
                                    "lastUpTime": "n/a",
                                    "vrf": vrf,
                                    "flag": "static",
                                }
                            )

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):
        """NXOS data returned from the textfsm
        template must be munged to a different format"""
        timestamp = raw_data[0]["timestamp"]

        for entry in processed_data:
            if not entry.get("flag"):
                entry.update({"flag": "n/a"})
            else:
                if "D" in entry["flag"]:
                    entry["flag"] = "dynamic"
                elif "S" in entry["flag"]:
                    entry["flag"] = "static"
            entry["lastUpTime"] = get_timestamp_from_cisco_time(
                entry["lastUpTime"], timestamp / 1000
            )

        return processed_data
