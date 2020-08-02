from suzieq.poller.services.service import Service


class MlagService(Service):
    """MLAG service. Different class because output needs to be munged"""

    def _clean_cumulus_data(self, processed_data, raw_data):
        """Populate the different portlists and counts"""

        mlagDualPortsCnt = 0
        mlagSinglePortsCnt = 0
        mlagErrorPortsCnt = 0
        mlagDualPorts = []
        mlagSinglePorts = []
        mlagErrorPorts = []

        for entry in processed_data:
            if entry['state']:
                entry['state'] = 'active'
            else:
                entry['state'] = 'inactive'
            mlagIfs = entry["mlagInterfacesList"]
            for mlagif in mlagIfs:
                if mlagIfs[mlagif]["status"] == "dual":
                    mlagDualPortsCnt += 1
                    mlagDualPorts.append(mlagif)
                elif mlagIfs[mlagif]["status"] == "single":
                    mlagSinglePortsCnt += 1
                    mlagSinglePorts.append(mlagif)
                elif (
                    mlagIfs[mlagif]["status"] == "errDisabled"
                    or mlagif["status"] == "protoDown"
                ):
                    mlagErrorPortsCnt += 1
                    mlagErrorPorts.append(mlagif)
            entry["mlagDualPortsList"] = mlagDualPorts
            entry["mlagSinglePortsList"] = mlagSinglePorts
            entry["mlagErrorPortsList"] = mlagErrorPorts
            entry["mlagSinglePortsCnt"] = mlagSinglePortsCnt
            entry["mlagDualPortsCnt"] = mlagDualPortsCnt
            entry["mlagErrorPortsCnt"] = mlagErrorPortsCnt
            del entry["mlagInterfacesList"]

        return processed_data
