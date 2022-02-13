import re
from datetime import timedelta, datetime
from dateparser import parse

from suzieq.poller.worker.services.service import Service
from suzieq.shared.utils import get_timestamp_from_junos_time


class DeviceService(Service):
    """Checks the uptime and OS/version of the node.
    This is specially called out to normalize the timestamp and handle
    timestamp diff
    """

    def __init__(self, name, defn, period, stype, keys, ignore_fields,
                 schema, queue, db_access, run_once):
        super().__init__(name, defn, period, stype, keys, ignore_fields,
                         schema, queue, db_access, run_once)
        self.ignore_fields.append("bootupTimestamp")

    def _common_data_cleaner(self, processed_data, raw_data):
        for entry in processed_data:
            entry['status'] = "alive"
            entry["address"] = raw_data[0]["address"]

        return processed_data

    def _clean_linux_data(self, processed_data, raw_data):

        for entry in processed_data:
            # We're assuming that if the entry doesn't provide the
            # bootupTimestamp field but provides the sysUptime field,
            # we fix the data so that it is always bootupTimestamp
            # TODO: Fix the clock drift
            if not entry.get("bootupTimestamp", None) and entry.get(
                    "sysUptime", None):
                entry["bootupTimestamp"] = int(
                    int(raw_data[0]["timestamp"])/1000 -
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
            entry['os'] = 'linux'

        return self._common_data_cleaner(processed_data, raw_data)

    def _clean_cumulus_data(self, processed_data, raw_data):
        for entry in processed_data:
            model = entry.get('_modelName', '')
            if model:
                entry['model'] = model
            uptime = entry.get('_uptime', '').split()
            if uptime:
                hr, mins, secs = uptime[-1].split(':')
                if len(uptime) > 1:
                    days = int(uptime[0])
                else:
                    days = 0
                uptime_delta = timedelta(days=days, hours=int(hr),
                                         minutes=int(mins),
                                         seconds=int(secs.split('.')[0]))
                entry['bootupTimestamp'] = int(
                    (int(raw_data[0]["timestamp"])/1000) -
                    uptime_delta.total_seconds())

        return self._common_data_cleaner(processed_data, raw_data)

    def _clean_sonic_data(self, processed_data, raw_data):
        processed_data = self._clean_linux_data(processed_data, raw_data)
        # Sonic specific updates
        for entry in processed_data:
            entry['os'] = 'sonic'
            entry['vendor'] = entry['model'].split('-')[0]

        return processed_data

    def _clean_common_ios(self, entry, os):
        '''Common IOS-like NOS cleaning'''
        entry['os'] = os
        entry['vendor'] = 'Cisco'
        if entry.get('bootupTimestamp', ''):
            entry['bootupTimestamp'] = int(datetime.utcfromtimestamp(
                parse(entry['bootupTimestamp']).timestamp()).timestamp())

    def _clean_iosxr_data(self, processed_data, raw_data):
        for entry in processed_data:
            self._clean_common_ios(entry, 'iosxr')
            if 'IOS-XRv' in entry.get('model', ''):
                entry['architecture'] = "x86-64"

        return self._common_data_cleaner(processed_data, raw_data)

    def _clean_iosxe_data(self, processed_data, raw_data):
        for entry in processed_data:
            self._clean_common_ios(entry, 'iosxe')

        return self._common_data_cleaner(processed_data, raw_data)

    def _clean_ios_data(self, processed_data, raw_data):
        for entry in processed_data:
            self._clean_common_ios(entry, 'ios')

        return self._common_data_cleaner(processed_data, raw_data)

    def _clean_junos_data(self, processed_data, raw_data):

        for entry in processed_data:
            entry['bootupTimestamp'] = get_timestamp_from_junos_time(
                entry['bootupTimestamp'],
                int(raw_data[0]["timestamp"])/1000)/1000

        return self._common_data_cleaner(processed_data, raw_data)

    def _clean_nxos_data(self, processed_data, raw_data):
        for entry in processed_data:
            upsecs = (24*3600*int(entry.pop('kern_uptm_days', 0)) +
                      3600*int(entry.pop('kern_uptm_hrs', 0)) +
                      60*int(entry.pop('kern_uptm_mins', 0)) +
                      int(entry.pop('kern_uptm_secs', 0)))
            if upsecs:
                entry['bootupTimestamp'] = int(
                    int(raw_data[0]["timestamp"])/1000 - upsecs)

        return self._common_data_cleaner(processed_data, raw_data)

    def _clean_panos_data(self, processed_data, raw_data):
        for entry in processed_data:
            upsecs = None
            match = re.search(
                r'(\d+)\sdays,\s(\d+):(\d+):(\d+)',
                entry.get('_uptime'))
            if match:
                days = match.group(1).strip()
                hours = match.group(2).strip()
                minutes = match.group(3).strip()
                seconds = match.group(4).strip()
                upsecs = 86400 * int(days) + 3600 * int(hours) + \
                    60 * int(minutes) + int(seconds)
            if upsecs:
                entry['bootupTimestamp'] = int(
                    int(raw_data[0]["timestamp"])/1000 - upsecs)
            # defaults
            entry["vendor"] = "Palo Alto"
            entry["os"] = "panos"
        return self._common_data_cleaner(processed_data, raw_data)
