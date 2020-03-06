from suzieq.poller.services.service import Service


class EvpnVniService(Service):
    """evpnVni service. Different class because output needs to be munged"""

    def clean_data(self, processed_data, raw_data):

        if raw_data.get("devtype", None) == "cumulus":
            for entry in processed_data:
                if entry["numRemoteVteps"] == "n/a":
                    entry["numRemoteVteps"] = 0
                if entry["remoteVteps"] == '':
                    entry["remoteVteps"] == []
        return super().clean_data(processed_data, raw_data)
