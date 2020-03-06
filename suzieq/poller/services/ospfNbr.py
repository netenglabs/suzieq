from datetime import datetime
from suzieq.poller.services.service import Service


class OspfNbrService(Service):
    """OSPF Neighbor service. Output needs to be munged"""

    def frr_convert_reltime_to_epoch(self, reltime):
        """Convert string of type 1d12h3m23s into absolute epoch"""
        secs = 0
        s = reltime
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

        return int((datetime.utcnow().timestamp() - secs) * 1000)

    def clean_data(self, processed_data, raw_data):

        dev_type = raw_data.get("devtype", None)
        if dev_type == "cumulus" or dev_type == "linux":
            for entry in processed_data:
                entry["vrf"] = "default"
                entry["state"] = entry["state"].lower()
                entry["lastChangeTime"] = self.frr_convert_reltime_to_epoch(
                    entry["lastChangeTime"]
                )
                entry["areaStub"] = entry["areaStub"] == "[Stub]"
        elif dev_type == "eos":
            for entry in processed_data:
                entry["state"] = entry["state"].lower()
                entry["lastChangeTime"] = int(entry["lastChangeTime"] * 1000)

        return super().clean_data(processed_data, raw_data)
