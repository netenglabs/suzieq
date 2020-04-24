from suzieq.poller.services.service import Service


class DeviceService(Service):
    """Checks the uptime and OS/version of the node.
    This is specially called out to normalize the timestamp and handle
    timestamp diff
    """

    def __init__(self, name, defn, period, stype, keys, ignore_fields,
                 schema, queue, run_once):
        super().__init__(name, defn, period, stype, keys, ignore_fields,
                         schema, queue, run_once)
        self.ignore_fields.append("bootupTimestamp")

    def clean_data(self, processed_data, raw_data):
        """Cleanup the bootup timestamp for Linux nodes"""

        for entry in processed_data:
            # We're assuming that if the entry doesn't provide the
            # bootupTimestamp field but provides the sysUptime field,
            # we fix the data so that it is always bootupTimestamp
            # TODO: Fix the clock drift
            if not entry.get("bootupTimestamp", None) and entry.get(
                    "sysUptime", None):
                entry["bootupTimestamp"] = int(
                    int(raw_data["timestamp"])/1000 -
                    float(entry.pop("sysUptime", 0))
                )
                if entry["bootupTimestamp"] < 0:
                    entry["bootupTimestamp"] = 0
            # This is the case for Linux servers, so also extract the vendor
            # and version from the os string
            if not entry.get("vendor", ''):
                if 'os' in entry:
                    osstr = entry.get("os", "").split()
                    if len(osstr) > 1:
                        # Assumed format is: Ubuntu 18.04.2 LTS,
                        # CentOS Linux 7 (Core)
                        entry["vendor"] = osstr[0]
                        if not entry.get("version", ""):
                            entry["version"] = ' '.join(osstr[1:])
                    del entry["os"]

            entry['status'] = "alive"
            entry["address"] = raw_data["address"]
        return super().clean_data(processed_data, raw_data)

    def get_diff(self, old, new):
        """Compare list of dictionaries ignoring certain fields
        Return list of adds and deletes.
        Need a special one for device because of bootupTimestamp
        whose time varies by a few msecs each time the poller runs,
        skewing the data and making us update service records each
        time. So, we mark bootupTimestamp to be ignored, and we
        do an additional check where we check the actual diff in
        the value between old and new records.
        """
        adds, dels = super().get_diff(old, new)
        if not (adds or dels):
            # Verify the bootupTimestamp hasn't changed. Compare only int part
            # Assuming no device boots up in millisecs
            if abs(int(new[0]["bootupTimestamp"]) -
                   int(old[0]["bootupTimestamp"])) > 2:
                adds.append(new[0])

        return adds, dels
