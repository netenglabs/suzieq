from suzieq.poller.services.service import Service


class BgpService(Service):
    """bgp service. Different class because minor munging of output due to versions"""

    def clean_data(self, processed_data, raw_data):

        processed_data = super().clean_data(processed_data, raw_data)

        # The AFI/SAFI key string changed in version 7.x of FRR and so we have
        # to munge the output to get the data out of the right key_fields
        if raw_data.get("devtype", None) == "eos":
            processed_data = self._clean_eos_data(processed_data, raw_data)
        elif raw_data.get("devtype", None) == "junos":
            processed_data = self._clean_junos_data(processed_data, raw_data)

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
