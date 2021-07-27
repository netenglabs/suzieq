from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from dateparser import parse

import numpy as np

from suzieq.poller.services.service import Service
from suzieq.utils import get_timestamp_from_cisco_time
from suzieq.utils import get_timestamp_from_junos_time


class OspfNbrService(Service):
    """OSPF Neighbor service. Output needs to be munged"""

    def frr_convert_reltime_to_epoch(self, reltime, timestamp):
        """Convert string of type 1d12h3m23s into absolute epoch"""
        secs = 0
        s = reltime
        if not reltime:
            return 0

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

        return int((timestamp/1000) - secs) * 1000

    def _clean_linux_data(self, processed_data, raw_data):

        if not raw_data:
            return processed_data

        if isinstance(raw_data, list):
            read_from = raw_data[0]
        else:
            read_from = raw_data
        timestamp = read_from["timestamp"]

        for entry in processed_data:
            entry["vrf"] = "default"
            entry["state"] = entry["state"].lower()
            entry["lastUpTime"] = self.frr_convert_reltime_to_epoch(
                entry["lastUpTime"], timestamp
            )
            entry["lastDownTime"] = self.frr_convert_reltime_to_epoch(
                entry["lastDownTime"], timestamp
            )
            if entry["lastUpTime"] > entry["lastDownTime"]:
                entry["lastChangeTime"] = entry["lastUpTime"]
            else:
                entry["lastChangeTime"] = entry["lastDownTime"]
            entry["areaStub"] = entry["areaStub"] == "[Stub]"
            if not entry["bfdStatus"]:
                entry["bfdStatus"] = "disabled"
            else:
                entry["bfdStatus"] = entry['bfdStatus'].lower()

        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)

    def _clean_eos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry["state"] = entry["state"].lower()
            entry["lastChangeTime"] = int(entry["lastChangeTime"] * 1000)
            # What is provided is the opposite of stub and so we not it
            entry["areaStub"] = not entry["areaStub"]

            bfd_status = entry.get("bfdStatus", '')
            if not bfd_status or (bfd_status == 'adminDown'):
                entry["bfdStatus"] = "disabled"
            else:
                entry["bfdStatus"] = bfd_status.lower()

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):

        ifentries = {}
        drop_indices = []

        for i, entry in enumerate(processed_data):
            if entry.get('_entryType', '') == '_bfdType':
                ifname = entry.get('ifname', '')
                if ifentries.get(ifname, {}):
                    if any('OSPF' in x for x in entry['_client']):
                        ifentry = ifentries[ifname]
                        ifentry['bfdStatus'] = entry['bfdStatus'].lower()
                drop_indices.append(i)
                continue

            vrf = entry['vrf'][0]['data']
            if vrf == "master":
                entry['vrf'] = "default"
            else:
                entry['vrf'] = vrf

            entry['lastChangeTime'] = get_timestamp_from_junos_time(
                entry['lastChangeTime'], raw_data[0]['timestamp']/1000)
            entry['state'] = entry['state'].lower()
            entry['bfdStatus'] = 'disabled'
            ifentries[entry['ifname']] = entry

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):
        for entry in processed_data:
            entry['state'] = entry['state'].lower()
            entry['numChanges'] = int(entry['numChanges'])
            # Cisco's format examples are PT7H28M21S, P1DT4H9M46S
            entry['lastChangeTime'] = get_timestamp_from_cisco_time(
                entry['lastChangeTime'], raw_data[0]['timestamp']/1000)

            if not entry.get("bfdStatus", ''):
                entry["bfdStatus"] = "disabled"
            else:
                entry["bfdStatus"] = entry['bfdStatus'].lower()
        return processed_data

    def _clean_ios_data(self, processed_data, raw_data):
        for entry in processed_data:
            # make area the dotted model
            area = entry.get('area', '')
            if area.isdecimal():
                entry['area'] = str(ip_address(int(area)))
            entry['state'] = entry['state'].lower()
            entry['lastUpTime'] = parse(entry['lastUpTime']).timestamp()
            entry['lastChangeTime'] = int(entry['lastUpTime'])*1000
            entry['lastDownTime'] = 0
            entry['lsaRtxCnt'] = int(entry['lsaRetxCnt'])
            entry['areaStub'] = entry['areaStub'] == 'Stub'
            entry['vrf'] = "default"
            entry['nbrPrio'] = int(entry['nbrPrio']) if entry['nbrPrio'] else 0
            if not entry.get("bfdStatus", ''):
                entry["bfdStatus"] = "unknown"
            else:
                entry["bfdStatus"] = entry['bfdStatus'].lower()

        return processed_data

    def _clean_iosxe_data(self, processed_data, raw_data):
        return self._clean_ios_data(processed_data, raw_data)
