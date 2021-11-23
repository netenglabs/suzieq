from suzieq.poller.services.service import Service
from suzieq.utils import expand_nxos_ifname


class MlagService(Service):
    """MLAG service. Different class because output needs to be munged"""

    def clean_json_input(self, data):
        """FRR JSON data needs some work"""

        devtype = data.get("devtype", None)
        if devtype in ["nxos"]:
            if data['data'].startswith('Note: \n'):
                lines = data['data'].splitlines()
                if len(lines) > 3:
                    data['data'] = '\n'.join(lines[2:])
                else:
                    data['data'] = ('{\n"TABLE_orphan_ports": \n{\n'
                                    '"ROW_orphan_ports": [\n]\n}\n}\n\n')
                return data['data']

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

    def _clean_nxos_data(self, processed_data, raw_data):
        """NXOS VPC data massaging"""

        mlagDualPorts = []
        mlagSinglePorts = []
        mlagErrorPorts = []

        if not processed_data:
            return processed_data

        for entry in processed_data:
            # systemID is a mandatory parameter
            domainid = entry.get('domainId', '')
            if not domainid or (domainid == 'not configured'):
                processed_data = []
                return processed_data

            mlagSinglePorts = list(filter(
                lambda x: x == '1',
                entry.get('_forwardViaPeerLinkList', []) or []))
            mlagErrorPorts = list(filter(
                lambda x: x != 'consistent',
                entry.get('_portConfigSanityList', []) or []))
            mlagDualPorts = entry.get('_portList', []) or []
            mlagDualPorts = list(filter(
                lambda x: x not in mlagSinglePorts and x not in mlagErrorPorts,
                mlagDualPorts))

            if entry.get('peerLinkStatus', '') == 1:
                entry['peerLinkStatus'] = 'up'
            else:
                entry['peerLinkStatus'] = 'down'
            entry['peerLink'] = expand_nxos_ifname(entry['peerLink'])
            entry['peerAddress'] = entry.get('peerAddress', [])
            entry['mlagDualPortsList'] = mlagDualPorts
            entry['mlagDualPortsCnt'] = len(mlagDualPorts)
            entry['mlagSinglePortsList'] = mlagSinglePorts
            entry['mlagSinglePortsCnt'] = len(mlagSinglePorts)
            entry['mlagErrorPortsList'] = mlagErrorPorts
            entry['mlagErrorPortsCnt'] = len(mlagErrorPorts)
            entry['state'] = 'active' if entry['state'] == 'peer-ok' \
                else 'dead'
            if entry['configSanity'] != 'consistent':
                entry['configSanity'] = entry['_reason']

        return processed_data

    def _clean_eos_data(self, processed_data, raw_data):
        '''EOS MLAG data massaging'''

        for entry in processed_data:
            # There's no MLAG without systemID
            if not entry['systemId']:
                return []

            entry['mlagDualPortsList'] = []
            entry['mlagSinglePortsList'] = []
            entry['mlagErrorPortsList'] = []

            for port_info in zip(entry.get('_localInterfaceList', []),
                                 entry.get('_linkStateList', [])):
                if port_info[1] == 'active-full':
                    entry['mlagDualPortsList'].append(port_info[0])
                elif port_info[1] == 'active-partial':
                    entry['mlagSinglePortsList'].append(port_info[0])
                elif port_info[1] in ['disabled', 'inactive']:
                    entry['mlagErrorPortsList'].append(port_info[0])

        return processed_data
