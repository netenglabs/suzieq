from suzieq.poller.services.service import Service


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
        elif raw_data.get("devtype", None) == "eos":
            for entry in processed_data:
                entry["networkType"] = entry["networkType"].lower()
                entry["isUnnumbered"] = False
        return super().clean_data(processed_data, raw_data)
