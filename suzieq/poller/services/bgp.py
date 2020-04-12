from suzieq.poller.services.service import Service


class BgpService(Service):
    """bgp service. Different class because minor munging of output due to versions"""

    def clean_data(self, processed_data, raw_data):

        processed_data = super().clean_data(processed_data, raw_data)

        # The AFI/SAFI key string changed in version 7.x of FRR and so we have
        # to munge the output to get the data out of the right key_fields
        if raw_data.get("devtype", None) == "eos":
            return self._clean_eos_data(processed_data, raw_data)

        return processed_data

    def _clean_eos_data(self, processed_data, raw_data):

        for entry in processed_data:
            if entry["bfdStatus"] == 3:
                entry["bfdStatus"] = "up"
            elif entry["bfdStatus"] != "disabled":
                entry["bfdStatus"] = "down"
            entry["asn"] = int(entry["asn"])
            entry["peerAsn"] = int(entry["peerAsn"])

        return processed_data
