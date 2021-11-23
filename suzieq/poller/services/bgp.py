import re
import numpy as np
from dateparser import parse
from datetime import datetime
from copy import deepcopy

from suzieq.poller.services.service import Service
from suzieq.utils import get_timestamp_from_cisco_time
from suzieq.utils import get_timestamp_from_junos_time


class BgpService(Service):
    """bgp service. Different class because of munging of output across NOS"""

    def _clean_eos_data(self, processed_data, raw_data):

        new_entries = []
        drop_indices = []

        for j, entry in enumerate(processed_data):

            if entry.get('state', '') != 'Established':
                entry['state'] = 'NotEstd'
                entry['afi'] = entry['safi'] = ''
                if not entry.get('bfdStatus', ''):
                    entry['bfdStatus'] = ''
                if (entry.get('holdTime', '0') == '0' and
                        entry.get('configHoldtime', '')):
                    entry['holdTime'] = entry['configHoldtime']
                    entry['keepaliveTime'] = entry['configKeepalive']
                continue

            estdTime = parse(
                entry.get('estdTime', ''),
                settings={'RELATIVE_BASE':
                          datetime.fromtimestamp(
                              (raw_data[0]['timestamp'])/1000), })

            if 'EVPN' in entry.get('afi', []):
                afidx = entry['afi'].index('EVPN')
                entry['safi'].insert(afidx, 'evpn')

            entry['afi'] = ['l2vpn' if x == "EVPN" else x.lower()
                            for x in entry.get('afi', [])]
            entry['safi'] = ['flowspec' if x == "Flow Specification"
                             else x.lower() for x in entry.get('safi', [])]

            bfd_status = entry.get('bfdStatus', 'disabled').lower()
            if not bfd_status or (bfd_status == "unknown"):
                bfd_status = "disabled"
            entry['bfdStatus'] = bfd_status

            for i, afi in enumerate(entry['afi']):
                if 'sr-te' in entry['safi'][i]:
                    # SR-TE is not really an AFI/SAFI, and we don't do SR-TE
                    # at this point. Full investigation of SR-TE is for later
                    continue
                new_entry = deepcopy(entry)
                new_entry['afi'] = afi
                new_entry['safi'] = entry['safi'][i]
                new_entry['pfxTx'] = entry['pfxTx'][i]
                new_entry['pfxRx'] = entry['pfxRx'][i]
                if entry.get('rrclient', ''):
                    new_entry['rrclient'] = True
                else:
                    new_entry['rrclient'] = False
                new_entry['estdTime'] = int(estdTime.timestamp()*1000)
                if entry['pfxBestRx']:
                    # Depending on the moodiness of the output, this field
                    # may not be present. So, ignore it.
                    new_entry['pfxBestRx'] = entry['pfxBestRx'][i]

                new_entry['defOriginate'] = False
                if 'safi' == 'evpn':
                    if ('Sending extended community not configured' in
                            entry.get('errorMsg', '')):
                        new_entry['communityTypes'] = []
                    else:
                        new_entry['communityTypes'] = ['standard', 'extended']
                else:
                    new_entry['communityTypes'] = ['standard']
                if entry.get('hopsMax', '').isnumeric():
                    # Older versions of EOS don't provide this field
                    new_entry['hopsMax'] = int(entry.get('hopsMax', 255))-255
                else:
                    new_entry['hopsMax'] = -1
                try:
                    afidx = entry.get('iMapafisafi', []).index(afi)
                    new_entry['ingressRmap'] = entry.get('ingressRmap')[afidx]
                except (ValueError, AttributeError):
                    new_entry['ingressRmap'] = ''
                try:
                    afidx = entry.get('oMapafisafi', []).index(afi)
                    new_entry['egressRmap'] = entry.get('egressRmap')[afidx]
                except (ValueError, AttributeError):
                    new_entry['egressRmap'] = ''

                new_entries.append(new_entry)
            drop_indices.append(j)

        processed_data += new_entries
        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):

        def _rename_afi_safi(afistr: str) -> str:
            if afistr == "l2vpn":
                afistr = "l2vpn-vpls"
            elif afistr == "l2vpn-signaling":
                afistr = "l2vpn-vpws"

            afistr = (afistr
                      .replace('inet-vpn', 'vpnv4')
                      .replace('inet6-vpn', 'vpnv6')
                      .replace('-', ' ')
                      .replace('inet6', 'ipv6')
                      .replace('inet', 'ipv4')
                      .replace('flow', 'flowspec')
                      .replace('evpn', 'l2vpn evpn'))

            return afistr

        peer_uptimes = {}
        drop_indices = []
        new_entries = []

        for i, entry in enumerate(processed_data):
            if entry['_entryType'] == 'summary':
                peer_uptimes[entry['peer']] = entry['estdTime']
                drop_indices.append(i)
                continue

            bfd_status = entry.get('bfdStatus', '')
            if not bfd_status or (bfd_status == "unknown"):
                bfd_status = "disabled"
            elif entry.get('_bfdAdmin', '') != 'enabled':
                bfd_status = "disabled"
            else:
                bfd_status = bfd_status.lower()
            entry['bfdStatus'] = bfd_status

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

            if entry.get('rrclient', ''):
                entry['rrclient'] = True
            else:
                entry['rrclient'] = False
            advafis = set(entry['afiSafiAdvList'].split())
            rcvafis = set(entry['afiSafiRcvList'].split())

            entry['afisAdvOnly'] = list(advafis.difference(rcvafis))
            entry['afisRcvOnly'] = list(rcvafis.difference(advafis))
            entry['afisAdvOnly'] = list(map(_rename_afi_safi,
                                            entry['afisAdvOnly']))
            entry['afisRcvOnly'] = list(map(_rename_afi_safi,
                                            entry['afisRcvOnly']))

            # Junos doesn't provide this data in neighbor, only in summary
            entry['estdTime'] = get_timestamp_from_junos_time(
                entry['estdTime'], raw_data[0]['timestamp']/1000)

            if entry['state'] != 'Established':
                entry['afi'] = entry['safi'] = ''
                continue

            # Build the mapping between pfx counts with the AFI/SAFI
            # Assign counts to appropriate AFi/SAFI
            table_afi_map = {}
            for x in zip(entry['_tableAfiList'], entry['_tableNameList']):
                table_afi_map.setdefault(x[0], []).append(x[1])

            pfxrx_list = dict(zip(entry['_pfxType'], entry['_pfxRxList']))
            pfxtx_list = dict(zip(entry['_pfxType'], entry['_pfxTxList']))
            pfxsupp_list = dict(
                zip(entry['_pfxType'], entry['_pfxSuppressList']))
            pfxbest_list = dict(
                zip(entry['_pfxType'], entry['_pfxBestRxList']))

            for orig_elem in table_afi_map:
                # Junos names its VRFs thus: VRFA.inet.0
                # and we want to strip off the .inet.0 part (Bug #404)
                new_entry = deepcopy(entry)
                elem = _rename_afi_safi(orig_elem)
                afi, safi = elem.split()
                new_entry['afi'] = afi
                new_entry['safi'] = safi
                new_entry['pfxRx'] = 0
                new_entry['pfxTx'] = 0
                new_entry['pfxBestRx'] = 0
                new_entry['pfxSuppressRx'] = 0
                for table in table_afi_map[orig_elem]:
                    vrf = table
                    if vrf == "inet.0":
                        vrf = "default"
                    elif vrf == "inet6.0":
                        vrf = "default"
                    elif vrf == "bgp.evpn.0":
                        vrf = "default"
                    elif vrf.startswith(('__default_evpn__.',
                                         'default-switch.')):
                        continue
                    else:
                        vrf = vrf.split('.')[0]
                    new_entry['vrf'] = vrf
                    new_entry['pfxRx'] += int(pfxrx_list.get(table, 0) or 0)
                    new_entry['pfxTx'] += int(pfxtx_list.get(table, 0) or 0)
                    new_entry['pfxSuppressRx'] += int(pfxsupp_list.get(table,
                                                                       0) or 0)
                    new_entry['pfxBestRx'] += int(
                        pfxbest_list.get(table, 0) or 0)
                new_entry['communityTypes'] = ['standard', 'extended']

                new_entry.pop('_pfxType')
                new_entry.pop('_pfxRxList')
                new_entry.pop('_pfxTxList')
                new_entry.pop('_pfxSuppressList')
                new_entry.pop('_tableAfiList')
                new_entry.pop('_tableNameList')
                new_entries.append(new_entry)

            drop_indices.append(i)

        processed_data += new_entries
        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):

        entries_by_vrf = {}
        drop_indices = []
        new_entries = []        # To add the AFI/SAFI-based entries

        for j, entry in enumerate(processed_data):
            if entry['_entryType'] == 'summary':
                for ventry in entries_by_vrf.get(entry['vrf'], []):
                    ventry['asn'] = entry['asn']
                    ventry['routerId'] = entry['routerId']
                drop_indices.append(j)
                continue

            bfd_status = entry.get('bfdStatus', '').lower()
            if bfd_status == "true":
                entry['bfdStatus'] = 'up'
            elif bfd_status != "disabled":
                entry['bfdStatus'] = 'down'

            if (entry.get('extnhAdvertised', False) == "true" and
                    entry.get('extnhReceived', False) == "true"):
                entry['extnhEnabled'] = True
            else:
                entry['extnhEnabled'] = False

            entry['estdTime'] = get_timestamp_from_cisco_time(
                entry['estdTime'], raw_data[0]['timestamp']/1000)
            if entry['vrf'] not in entries_by_vrf:
                entries_by_vrf[entry['vrf']] = []

            if not entry['peer']:
                if not entry.get('_dynPeer', None):
                    drop_indices.append(j)
                    continue
                entry['peer'] = entry['_dynPeer'].replace('/', '-')
                entry['origPeer'] = entry['_dynPeer']
                entry['state'] = 'dynamic'
                entry['pfxRx'] = entry['_activePeers']
                entry['pfxTx'] = entry['_maxconcurrentpeers']
                entry['afi'] = entry['safi'] = 'dynamic'
                entry['estdTime'] = entry['_firstconvgtime']

            if entry['state'] != 'Established':
                entry.pop('afiPrefix')
                entry.pop('pfxRcvd')
                entry.pop('pfxSent')
                entry.pop('sendComm')
                entry.pop('extendComm')
                entry.pop('defaultOrig')
                entry.pop('afiSafi')
                entry['afi'] = entry['safi'] = ''
                entries_by_vrf[entry['vrf']].append(entry)
                continue

            entry['afisAdvOnly'] = []
            entry['afisRcvOnly'] = []
            for i, item in enumerate(entry['afiSafi']):
                if entry['afAdvertised'][i] != entry['afRcvd'][i]:
                    if entry['afAdvertised'][i] == 'true':
                        entry['afisAdvOnly'].append(entry['afiSafi'])
                    else:
                        entry['afisRcvOnly'].append(entry['afiSafi'])

            entry.pop('afiSafi')
            entry.pop('afAdvertised')
            entry.pop('afRcvd')

            if entry.get('rrclient', ''):
                entry['rrclient'] = 'True'
            else:
                entry['rrclient'] = 'False'

            defint_list = [0]*len(entry.get('afiPrefix', []))
            defbool_list = [False]*len(entry.get('afiPrefix', []))
            defstr_list = [""]*len(entry.get('afiPrefix', []))
            pfxRx_list = entry.get('pfxRcvd', []) or defint_list
            pfxTx_list = entry.get('pfxSent', []) or defint_list
            deforig_list = entry.get('defaultOrig', []) or defbool_list
            extcomm_list = entry.get('extendComm', []) or defbool_list
            comm_list = entry.get('sendComm', []) or defbool_list
            withdrawn_list = entry.get('pfxWithdrawn', []) or defint_list
            softrecon_list = entry.get('softReconfig', []) or defbool_list
            irmap_list = entry.get('ingressRmap', []) or defstr_list
            ermap_list = entry.get('egressRmap', []) or defstr_list

            for i, item in enumerate(entry['afiPrefix']):
                new_entry = deepcopy(entry)
                new_entry['afi'], new_entry['safi'] = \
                    [x.lower() for x in item.split()]
                new_entry['pfxRx'] = pfxRx_list[i]
                new_entry['pfxTx'] = pfxTx_list[i]
                new_entry['pfxWithdrawn'] = withdrawn_list[i]
                new_entry['softReconfig'] = softrecon_list[i]
                new_entry['defOriginate'] = deforig_list[i]
                new_entry['communityTypes'] = []
                if comm_list[i]:
                    new_entry['communityTypes'].append('standard')
                if extcomm_list[i] == "true":
                    new_entry['communityTypes'].append('extended')
                new_entry['ingressRmap'] = irmap_list[i]
                new_entry['egressRmap'] = ermap_list[i]
                new_entry.pop('afiPrefix')
                new_entry.pop('pfxRcvd')
                new_entry.pop('pfxSent')
                new_entry.pop('sendComm')
                new_entry.pop('extendComm')
                new_entry.pop('defaultOrig')

                new_entries.append(new_entry)
                entries_by_vrf[new_entry['vrf']].append(new_entry)
            drop_indices.append(j)

        processed_data += new_entries
        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_iosxr_data(self, processed_data, raw_data):

        drop_indices = []
        vrf_rtrid = {}

        # The last two entries are routerIds. Extract them first
        for i, entry in enumerate(reversed(processed_data)):
            if not entry.get('_entryType', ''):
                break

            vrf_rtrid.update({entry.get('vrf', 'default') or 'default':
                              entry.get('routerId', '')})

        for i, entry in enumerate(processed_data):
            if entry.get('_entryType', ''):
                drop_indices.append(i)
                continue

            bfd_status = entry.get('bfdStatus', 'disabled').lower()
            if not bfd_status or (bfd_status == "unknown"):
                bfd_status = "disabled"
            entry['bfdStatus'] = bfd_status

            if entry.get('state', '') != 'Established':
                entry['state'] = 'NotEstd'

            communities = []
            for comm in entry.get('communityTypes', []):
                if comm == "Community":
                    communities.append('standard')
                elif comm == 'Extended':
                    communities.append('extended')
            entry['communityTypes'] = communities
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
            entry['routerId'] = vrf_rtrid.get(entry['vrf'], '')
            if entry.get('rrclient', '') == '':
                entry['rrclient'] = 'False'
            else:
                entry['rrclient'] = 'True'

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_cumulus_data(self, processed_data, raw_data):

        new_entries = []
        drop_indices = []

        for i, entry in enumerate(processed_data):
            if entry['state'] != 'Established':
                continue

            bfd_status = entry.get('bfdStatus', 'disabled').lower()
            if not bfd_status or (bfd_status == "unknown"):
                bfd_status = "disabled"
            entry['bfdStatus'] = bfd_status

            for afi in entry.get('_afiInfo', {}):
                if afi in (entry.get('afisAdvOnly', []) or []):
                    continue

                new_entry = deepcopy(entry)
                if 'evpn' in afi.lower():
                    new_entry['afi'] = 'l2vpn'
                    new_entry['safi'] = 'evpn'
                else:
                    if ' ' in afi:
                        newafi, newsafi = afi.split()
                        new_entry['afi'] = newafi.lower().strip()
                        new_entry['safi'] = newsafi.lower().strip()
                    elif afi.startswith('ipv4'):
                        if 'Vpn' in afi:
                            new_entry['afi'] = 'vpnv4'
                            new_entry['safi'] = 'unicast'
                        else:
                            new_entry['afi'] = 'ipv4'
                            new_entry['safi'] = afi.split('ipv4')[1].lower()
                    elif afi.startswith('ipv6'):
                        if 'Vpn' in afi:
                            new_entry['afi'] = 'vpnv6'
                            new_entry['safi'] = 'unicast'
                        else:
                            new_entry['afi'] = 'ipv6'
                            new_entry['safi'] = afi.split('ipv6')[1].lower()

                subent = entry['_afiInfo'][afi]
                comm = subent.get('commAttriSentToNbr', '')
                if comm == 'extendedAndStandard':
                    new_entry['communityTypes'] = ['standard', 'extended']
                elif comm == 'standard':
                    new_entry['communityTypes'] = ['standard']

                if 'routeReflectorClient' in subent:
                    new_entry['rrclient'] = 'True'
                else:
                    new_entry['rrclient'] = 'False'
                new_entry['pfxRx'] = subent.get('acceptedPrefixCounter', 0)
                new_entry['pfxTx'] = subent.get('sentPrefixCounter', 0)
                new_entry['ingressRmap'] = \
                    subent.get('routeMapForIncomingAdvertisements', '')
                new_entry['egressRmap'] = \
                    subent.get('routeMapForOutgoingAdvertisements', '')
                new_entry['defOriginate'] = 'defaultSent' in subent or False
                new_entry['advertiseAllVnis'] = ('advertiseAllVnis' in subent
                                                 or False)
                new_entry['nhUnchanged'] = \
                    'unchangedNextHopPropogatedToNbr' in subent or False

                new_entries.append(new_entry)

            drop_indices.append(i)

        processed_data += new_entries
        processed_data = np.delete(processed_data, drop_indices).tolist()

        return processed_data

    def _clean_linux_data(self, processed_data, raw_data):

        return self._clean_cumulus_data(processed_data, raw_data)

    def _clean_ios_data(self, processed_data, raw_data):

        drop_indices = []
        vrf_peer_dict = {}

        for i, entry in enumerate(processed_data):
            check_peer_key = f"{entry['peer']}-{entry['peerAsn']}"
            if entry.get('_entryType', ''):
                drop_indices.append(i)
                # Find the matching entry in the already processed data
                if check_peer_key in vrf_peer_dict:
                    # loop to add Router ID and ASN in all the registries
                    for index, item in enumerate(
                            vrf_peer_dict[check_peer_key]):
                        old_entry = vrf_peer_dict[check_peer_key]
                        old_entry[index]['routerId'] = entry['routerId']
                        old_entry[index]['asn'] = entry['asn']
                        # add the prefix only in matching AFI-SAFI
                        if entry['afi'].lower() == (
                            old_entry[index]['afi'] and
                            entry['safi'].lower() == old_entry[index]['safi']
                        ):
                            old_entry[index]['pfxRx'] = entry['statePfx']
                continue
            else:
                if check_peer_key not in vrf_peer_dict:
                    vrf_peer_dict[check_peer_key] = [entry]
                else:
                    vrf_peer_dict[check_peer_key].append(entry)

            bfd_status = entry.get('bfdStatus', 'disabled').lower()
            if not bfd_status or (bfd_status == "unknown"):
                bfd_status = "disabled"
            entry['bfdStatus'] = bfd_status

            entry['peerIP'] = entry['peer']
            if entry.get('state', '') != 'Established':
                entry['state'] = 'NotEstd'

            entry['communityTypes'] = []  # We don't parse this yet
            entry['numChanges'] = (int(entry.get('_numConnEstd', 0) or 0) +
                                   int(entry.get('_numConnDropped', 0) or 0))
            if not entry.get('vrf', ''):
                entry['vrf'] = 'default'
            if entry.get('afi', ''):
                entry['afi'] = entry['afi'].lower()
            if entry.get('safi', ''):
                entry['safi'] = entry['safi'].lower()
            # IOS gives uptime/downtime as hh:mm:ss string always
            # dateparser interprets this as a specific time, and so
            # we need to fix that
            estdTime = entry.get('estdTime', '')
            if estdTime:
                if re.match(r'^\d{2}:\d{2}:\d{2}$', estdTime):
                    estdTime = estdTime.split(':')
                    estdTime = (f'{estdTime[0]} hour '
                                '{estdTime[1]}:{estdTime[2]} mins ago')
                estdTime = parse(
                    estdTime,
                    settings={'RELATIVE_BASE':
                              datetime.fromtimestamp(
                                  (raw_data[0]['timestamp'])/1000), })
            if estdTime and estdTime != ['']:
                entry['estdTime'] = int(estdTime.timestamp()*1000)
            if entry.get('rrclient', '') == '':
                entry['rrclient'] = 'False'
            else:
                entry['rrclient'] = 'True'

            entry['afisAdvOnly'] = [x.lower()
                                    for x in entry.get('afisAdvOnly', [])]
            entry['afisRcvOnly'] = [x.replace('E-VPN', 'EVPN').lower()
                                    for x in entry.get('afisRcvOnly', [])]

        processed_data = np.delete(processed_data, drop_indices).tolist()
        return processed_data

    def _clean_iosxe_data(self, processed_data, raw_data):
        return self._clean_ios_data(processed_data, raw_data)

    def _clean_sonic_data(self, processed_data, raw_data):
        return self._clean_linux_data(processed_data, raw_data)
