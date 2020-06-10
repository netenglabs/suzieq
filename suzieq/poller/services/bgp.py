from suzieq.poller.services.service import Service
from suzieq.utils import build_cisco_timestring
from datetime import datetime


class BgpService(Service):
    """bgp service. Different class because minor munging of output due to versions"""

    def clean_data(self, processed_data, raw_data):

        devtype = self._get_devtype_from_input(raw_data)
        # The AFI/SAFI key string changed in version 7.x of FRR and so we have
        # to munge the output to get the data out of the right key_fields
        if devtype == "eos":
            processed_data = self._clean_eos_data(processed_data, raw_data)
        elif devtype == "junos":
            processed_data = self._clean_junos_data(processed_data, raw_data)
        elif devtype == "nxos":
            processed_data = self._clean_nxos_data(processed_data, raw_data)

        return super().clean_data(processed_data, raw_data)

    def _clean_eos_data(self, processed_data, raw_data):

        for entry in processed_data:
            if entry["bfdStatus"] == 3:
                entry["bfdStatus"] = "up"
            elif entry["bfdStatus"] != "disabled":
                entry["bfdStatus"] = "down"
            entry["asn"] = int(entry["asn"])
            entry["peerAsn"] = int(entry["peerAsn"])

        return processed_data

    def _clean_junos_data(self, processed_data, raw_data):

        for entry in processed_data:
            # JunOS adds entries which includes the port as IP+Port
            entry['peerIP'] = entry['peerIP'].split('+')[0]
            entry['updateSource'] = entry['updateSource'].split('+')[0]
            entry['numChanges'] = int(entry['numChanges'])
            entry['updatesRx'] = int(entry['updatesRx'])
            entry['updatesTx'] = int(entry['updatesTx'])
            entry['asn'] = int(entry['asn'])
            entry['peerAsn'] = int(entry['peerAsn'])
            entry['keepaliveTime'] = int(entry['keepaliveTime'])
            entry['holdTime'] = int(entry['holdTime'])

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

        return processed_data

    def _clean_nxos_data(self, processed_data, raw_data):

        for entry in processed_data:
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

            if entry['rrclient'][0] == "true":
                entry['rrClient'] = True

            for i, item in enumerate(entry['afiPrefix']):
                if item == 'IPv4 Unicast':
                    entry['v4PfxRx'] = entry['pfxRcvd'][i]
                    entry['v4PfxTx'] = entry['pfxSent'][i]
                    entry['v4DefaultSent'] = entry['defaultOrig'][i]
                elif item == 'IPv6 Unicast':
                    entry['v6PfxRx'] = entry['pfxRcvd'][i]
                    entry['v6PfxTx'] = entry['pfxSent'][i]
                    entry['v6DefaultSent'] = entry['defaultOrig'][i]
                elif item == 'L2VPN EVPN':
                    entry['evpnPfxRx'] = entry['pfxRcvd'][i]
                    entry['evpnPfxTx'] = entry['pfxSent'][i]
                    if entry['sendComm'][i] == "true":
                        if entry['extendComm'] == "true":
                            entry['evpnSendCommunity'] = 'extendedAndstandard'
                        else:
                            entry['evpnSendCommunity'] = 'standard'
                    elif entry['extendComm'] == "true":
                        entry['evpnSendCommunity'] = 'extended'
                    entry['evpnDefaultSent'] = entry['defaultOrig'][i]

            entry.pop('afiPrefix')
            entry.pop('pfxRcvd')
            entry.pop('pfxSent')
            entry.pop('sendComm')
            entry.pop('extendComm')
            entry.pop('defaultOrig')

            if (entry['extnhAdvertised'] == "true" and
                    entry['extnhReceived'] == "true"):
                entry['extnhEnabled'] = True
            else:
                entry['extnhEnabled'] = False

            uptime = entry['estdTime']
            period = datetime.strptime(uptime,
                                       build_cisco_timestring(uptime)).time()
            secs = period.hour*3600 + period.minute*60 + period.second
            entry['estdTime'] = raw_data[0]['timestamp'] - secs*1000

        return processed_data
