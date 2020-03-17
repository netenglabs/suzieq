from datetime import datetime
from suzieq.poller.services.service import Service, HOLD_TIME_IN_MSECS

import copy
import logging


class SystemService(Service):
    """Checks the uptime and OS/version of the node.
    This is specially called out to normalize the timestamp and handle
    timestamp diff
    """

    nodes_state = {}

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

    async def commit_data(self, result, datacenter, hostname):
        """system svc needs to write out a record that indicates dead node"""
        nodeobj = self.nodes.get(hostname, None)
        if not nodeobj:
            # This will be the case when a node switches from init state
            # to good after nodes have been built. Find the corresponding
            # node and fix the nodelist
            nres = [
                self.nodes[x] for x in self.nodes
                if self.nodes[x].hostname == hostname
            ]
            if nres:
                nodeobj = nres[0]
            else:
                logging.error(
                    "Ignoring results for {} which is not in "
                    "nodelist for service {}".format(hostname, self.name)
                )
                return

        if not result:
            if nodeobj.get_status() == "init":
                # If in init still, we need to mark the node as unreachable
                rec = self.get_empty_record()
                rec["datacenter"] = datacenter
                rec["hostname"] = hostname
                rec["timestamp"] = int(datetime.utcnow().timestamp() * 1000)
                rec["status"] = "dead"
                rec["active"] = True

                result.append(rec)
            elif nodeobj.get_status() == "good":
                # To avoid unnecessary flaps, we wait for HOLD_TIME to expire
                # before we mark the node as dead
                if hostname in self.nodes_state:
                    now = int(datetime.utcnow().timestamp() * 1000)
                    if now - self.nodes_state[hostname] > HOLD_TIME_IN_MSECS:
                        prev_res = nodeobj.prev_result
                        if prev_res:
                            result = copy.deepcopy(prev_res)
                        else:
                            record = self.get_empty_record()
                            record["datacenter"] = datacenter
                            record["hostname"] = hostname
                            result = [record]

                        result[0]["status"] = "dead"
                        result[0]["timestamp"] = self.nodes_state[hostname]
                        del self.nodes_state[hostname]
                        nodeobj.set_unreach_status()
                    else:
                        return
                else:
                    self.nodes_state[hostname] = int(
                        datetime.utcnow().timestamp() * 1000
                    )
                    return
            else:
                # Ensure we don't delete the dead entry
                prev_res = nodeobj.prev_result
                if prev_res:
                    result = copy.deepcopy(prev_res)
                    result[0]["timestamp"] = int(
                        datetime.utcnow().timestamp() * 1000
                    )
        else:
            # Clean up old state if any since we now have a valid output
            if self.nodes_state.get(hostname, None):
                del self.nodes_state[hostname]
            nodeobj.set_good_status()

        await super().commit_data(result, datacenter, hostname)

    def get_diff(self, old, new):
        """Compare list of dictionaries ignoring certain fields
        Return list of adds and deletes.
        Need a special one for system because of bootupTimestamp
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
