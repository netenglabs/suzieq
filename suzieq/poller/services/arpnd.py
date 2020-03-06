from suzieq.poller.services.service import Service


class ArpndService(Service):
    """arpnd service. Different class because minor munging of output"""

    def clean_data(self, processed_data, raw_data):

        devtype = raw_data.get("devtype", None)
        if any([devtype == x for x in ["cumulus", "linux", "platina"]]):
            for entry in processed_data:
                entry["offload"] = entry["offload"] == "offload"
                entry["state"] = entry["state"].lower()

        return super().clean_data(processed_data, raw_data)
