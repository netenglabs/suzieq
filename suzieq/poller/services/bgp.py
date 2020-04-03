from suzieq.poller.services.service import Service


class BgpService(Service):
    """bgp service. Different class because minor munging of output due to versions"""

    def clean_data(self, processed_data, raw_data):

        processed_data = super().clean_data(processed_data, raw_data)

        # The AFI/SAFI key string changed in version 7.x of FRR and so we have
        # to munge the output to get the data out of the right key_fields
        for entry in processed_data:
            if entry["state"] == "Established":
                if not (entry["v4Enabled"] or
                        entry["v6Enabled"] or entry["evpnEnabled"]):
                    # If there's a new AFI/SAFI outside of these four, we have
                    # to update this code!

                    if (entry.get("newv4Enabled", None) or
                            entry.get("newv6Enabled", None) or
                            entry.get("newevpnEnabled", None)):
                        entry["v4Enabled"] = entry.pop("newv4Enabled")
                        entry["v6Enabled"] = entry.pop("newv6Enabled")
                        entry["evpnEnabled"] = entry.pop("newevpnEnabled")
                        entry["v4PfxRx"] = entry.pop("newv4PfxRx")
                        entry["v6PfxRx"] = entry.pop("newv6PfxRx")
                        entry["evpnPfxRx"] = entry.pop("newevpnPfxRx")
        return processed_data
