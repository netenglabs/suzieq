from datetime import datetime, timedelta, timezone
from suzieq.poller.services.service import Service
from suzieq.utils import get_timestamp_from_cisco_time
from suzieq.utils import get_timestamp_from_junos_time


class OspfNbrService(Service):
    """OSPF Neighbor service. Output needs to be munged"""

    def frr_convert_reltime_to_epoch(self, reltime):
        """Convert string of type 1d12h3m23s into absolute epoch"""
        secs = 0
        s = reltime
        if not reltime:
            return 0

        for t, mul in {
            "w": 3600 * 24 * 7,
            "d": 3600 * 24,
            "h": 3600,
            "m": 60,
            "s": 1,
        }.items():
            v = s.split(t)
            if len(v) == 2:
                secs += int(v[0]) * mul
            s = v[-1]

        return int((datetime.now(tz=timezone.utc).timestamp() - secs) * 1000)

    def _clean_linux_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["vrf"] = "default"
            entry["state"] = entry["state"].lower()
            entry["lastUpTime"] = self.frr_convert_reltime_to_epoch(
                entry["lastUpTime"]
            )
            entry["lastDownTime"] = self.frr_convert_reltime_to_epoch(
                entry["lastDownTime"]
            )
            if entry["lastUpTime"] > entry["lastDownTime"]:
                entry["lastChangeTime"] = entry["lastUpTime"]
            else:
                entry["lastChangeTime"] = entry["lastDownTime"]
            entry["areaStub"] = entry["areaStub"] == "[Stub]"
            if not entry["bfdStatus"]:
                entry["bfdStatus"] = "disabled"

        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_eos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["state"] = entry["state"].lower()
            entry["lastChangeTime"] = int(entry["lastChangeTime"] * 1000)
            # What is provided is the opposite of stub and so we not it
            entry["areaStub"] = not entry["areaStub"]

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):
        for entry in processed_data:
            vrf = entry['vrf'][0]['data']
            if vrf == "master":
                entry['vrf'] = "default"
            else:
                entry['vrf'] = vrf

            entry['lastChangeTime'] = get_timestamp_from_junos_time(
                entry['lastChangeTime'], raw_data[0]['timestamp']/1000)
            entry['state'] = entry['state'].lower()

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry['state'] = entry['state'].lower()
            entry['numChanges'] = int(entry['numChanges'])
            # Cisco's format examples are PT7H28M21S, P1DT4H9M46S
            entry['lastChangeTime'] = get_timestamp_from_cisco_time(
                entry['lastChangeTime'], raw_data[0]['timestamp']/1000)

        return processed_data
