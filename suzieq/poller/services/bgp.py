import numpy as np
from dateparser import parse
from datetime import datetime

from suzieq.poller.services.service import Service
from suzieq.utils import get_timestamp_from_cisco_time
from suzieq.utils import get_timestamp_from_junos_time


class BgpService(Service):
    """bgp service. Different class because of munging of output across NOS"""

    def _clean_eos_data(self, processed_data, raw_data):

        for entry in processed_data:
            if entry["bfdStatus"] == 3:
                entry["bfdStatus"] = "up"
            elif entry["bfdStatus"] != "disabled":
                entry["bfdStatus"] = "down"
            entry["asn"] = int(entry["asn"])
            entry["peerAsn"] = int(entry["peerAsn"])
            entry['estdTime'] = raw_data[0]['timestamp'] - \
                (entry['estdTime']*1000)
            entry['origPeer'] = entry['peer']

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):

        peer_uptimes = {}
        drop_indices = []

        for i, entry in enumerate(processed_data):
            if entry['_entryType'] == 'summary':
                peer_uptimes[entry['peer']] = entry['estdTime']
                drop_indices.append(i)
                continue
            # JunOS adds entries which includes the port as IP+Port
            entry['peerIP'] = entry['peerIP'].split('+')[0]
            entry['peer'] = entry['peer'].split('+')[0]
            entry['updateSource'] = entry['updateSource'].split('+')[0]
            entry['numChanges'] = int(entry['numChanges'])
            entry['updatesRx'] = int(entry['updatesRx'])
            entry['updatesTx'] = int(entry['updatesTx'])
            entry['asn'] = int(entry['asn'])
            entry['peerAsn'] = int(entry['peerAsn'])
            entry['keepaliveTime'] = int(entry['keepaliveTime'])
            entry['holdTime'] = int(entry['holdTime'])

            if entry['peer'] in peer_uptimes:
                entry['estdTime'] = peer_uptimes[entry['peer']]
            else:
                entry['estdTime'] = '0d 00:00:00'

            # Assign counts to appropriate AFi/SAFI
            for i, afi in enumerate(entry.get('pfxType')):
                if entry['pfxRxList'][i] is None:
                    entry['pfxRxList'][i] = 0
                if afi == 'inet.0':
                    entry['v4PfxRx'] = int(entry['pfxRxList'][i])
                    entry['v4PfxTx'] = int(entry['pfxTxList'][i])
                    entry['v4Enabled'] = True
                elif afi == 'inet6.0':
                    entry['v6PfxRx'] = int(entry['pfxRxList'][i])
                    entry['v6PfxTx'] = int(entry['pfxTxList'][i])
                elif afi == 'bgp.evpn.0':
                    entry['evpnPfxRx'] = int(entry['pfxRxList'][i])
                    entry['evpnPfxTx'] = int(entry['pfxTxList'][i])

            entry.pop('pfxType')
            entry.pop('pfxRxList')
            entry.pop('pfxTxList')

            for afi in entry['afiSafiAdvList'].split():
                if afi == 'inet-unicast':
                    entry['v4Advertised'] = True
                elif afi == 'inet6-unicast':
                    entry['v6Advertised'] = True
                elif afi == 'evpn':
                    entry['evpnAdvertised'] = True
            entry.pop('afiSafiAdvList')

            for afi in entry['afiSafiRcvList'].split():
                if afi == 'inet-unicast':
                    entry['v4Received'] = True
                elif afi == 'inet6-unicast':
                    entry['v6Received'] = True
                elif afi == 'evpn':
                    entry['evpnReceived'] = True

            entry.pop('afiSafiRcvList')
            for afi in entry['afiSafiEnabledList'].split():
                if afi == 'inet-unicast':
                    entry['v4Enabled'] = True
                elif afi == 'inet6-unicast':
                    entry['v6Enabled'] = True
                elif afi == 'evpn':
                    entry['evpnEnabled'] = True

            entry.pop('afiSafiEnabledList')
            if not entry.get('vrf', None):
                entry['vrf'] = 'default'

            # Junos doesn't provide this data in neighbor, only in summary
            entry['estdTime'] = get_timestamp_from_junos_time(
                entry['estdTime'], raw_data[0]['timestamp']/1000)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):

        entries_by_vrf = {}
        drop_indices = []

        for i, entry in enumerate(processed_data):
            if entry['_entryType'] == 'summary':
                for ventry in entries_by_vrf.get(entry['vrf'], []):
                    ventry['asn'] = entry['asn']
                    ventry['routerId'] = entry['routerId']
                drop_indices.append(i)
                continue

            if not entry['peer']:
                if not entry.get('_dynPeer', None):
                    drop_indices.append(i)
                    continue
                entry['peer'] = entry['_dynPeer'].replace('/', '-')
                entry['origPeer'] = entry['_dynPeer']
                entry['state'] = 'dynamic'
                entry['v4PfxRx'] = entry['_activePeers']
                entry['v4PfxTx'] = entry['_maxconcurrentpeers']
                entry['estdTime'] = entry['_firstconvgtime']

            for i, item in enumerate(entry['afiSafi']):
                if item == 'IPv4 Unicast':
                    entry['v4Advertised'] = entry['afAdvertised'][i]
                    entry['v4Received'] = entry['afRcvd'][i]
                    if (entry['v4Advertised'] == "true" and
                            entry['v4Received'] == "true"):
                        entry['v4Enabled'] = True
                    else:
                        entry['v4Enabled'] = False
                elif item == 'IPv6 Unicast':
                    entry['v6Advertised'] = entry['afAdvertised'][i]
                    entry['v6Received'] = entry['afRcvd'][i]
                    if (entry['v6Advertised'] == "true" and
                            entry['v6Received'] == "true"):
                        entry['v6Enabled'] = True
                    else:
                        entry['v6Enabled'] = False
                elif item == 'L2VPN EVPN':
                    entry['evpnAdvertised'] = entry['afAdvertised'][i]
                    entry['evpnReceived'] = entry['afRcvd'][i]
                    if (entry['evpnAdvertised'] == "true" and
                            entry['evpnReceived'] == "true"):
                        entry['evpnEnabled'] = True
                    else:
                        entry['evpnEnabled'] = False

            entry.pop('afiSafi')
            entry.pop('afAdvertised')
            entry.pop('afRcvd')

            entry['rrClient'] = entry.get('rrclient', False) == "true"

            defint_list = [0]*len(entry.get('afiPrefix', []))
            defbool_list = [False]*len(entry.get('afiPrefix', []))
            pfxRx_list = entry.get('pfxRcvd', []) or defint_list
            pfxTx_list = entry.get('pfxSent', []) or defint_list
            deforig_list = entry.get('defaultOrig', []) or defbool_list
            extcomm_list = entry.get('extendComm', []) or defbool_list
            comm_list = entry.get('sendComm', []) or defbool_list

            for i, item in enumerate(entry['afiPrefix']):
                if item == 'IPv4 Unicast':
                    entry['v4PfxRx'] = pfxRx_list[i]
                    entry['v4PfxTx'] = pfxTx_list[i]
                    entry['v4DefaultSent'] = deforig_list[i]
                elif item == 'IPv6 Unicast':
                    entry['v6PfxRx'] = pfxRx_list[i]
                    entry['v6PfxTx'] = pfxTx_list[i]
                    entry['v6DefaultSent'] = deforig_list[i]
                elif item == 'L2VPN EVPN':
                    entry['evpnPfxRx'] = pfxRx_list[i]
                    entry['evpnPfxTx'] = pfxTx_list[i]
                    entry['evpnDefaultSent'] = deforig_list[i]
                    if comm_list[i] == "true":
                        if extcomm_list[i] == "true":
                            entry['evpnSendCommunity'] = 'extendedAndstandard'
                        else:
                            entry['evpnSendCommunity'] = 'standard'
                    elif extcomm_list[i] == "true":
                        entry['evpnSendCommunity'] = 'extended'

            entry.pop('afiPrefix')
            entry.pop('pfxRcvd')
            entry.pop('pfxSent')
            entry.pop('sendComm')
            entry.pop('extendComm')
            entry.pop('defaultOrig')

            if (entry.get('extnhAdvertised', False) == "true" and
                    entry.get('extnhReceived', False) == "true"):
                entry['extnhEnabled'] = True
            else:
                entry['extnhEnabled'] = False

            entry['estdTime'] = get_timestamp_from_cisco_time(
                entry['estdTime'], raw_data[0]['timestamp']/1000)
            if entry['vrf'] not in entries_by_vrf:
                entries_by_vrf[entry['vrf']] = []

            entries_by_vrf[entry['vrf']].append(entry)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_iosxr_data(self, processed_data, raw_data):

        drop_indices = []

        for i, entry in enumerate(processed_data):
            if not entry.get('afi', ''):
                drop_indices.append(i)
                continue

            entry['numChanges'] = (int(entry.get('_numConnEstd', 0) or 0) +
                                   int(entry.get('_numConnDropped', 0) or 0))
            if not entry.get('vrf', ''):
                entry['vrf'] = 'default'
            if entry.get('afi', ''):
                entry['afi'] = entry['afi'].lower()
            if entry.get('safi', ''):
                entry['safi'] = entry['safi'].lower()
            estdTime = parse(
                entry.get('estdTime', ''),
                settings={'RELATIVE_BASE':
                          datetime.fromtimestamp(
                              (raw_data[0]['timestamp'])/1000), })
            if estdTime:
                entry['estdTime'] = int(estdTime.timestamp()*1000)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data
