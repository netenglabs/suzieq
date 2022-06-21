import re
import numpy as np

from suzieq.shared.utils import expand_ios_ifname
from suzieq.poller.worker.services.service import Service


class InventoryService(Service):
    """Inventory service"""

    def _clean_data_common(self, processed_data, _):
        return processed_data

    def _clean_eos_data(self, processed_data, _):
        new_data = []
        for entry in processed_data:
            # Because of the JSON structure of the data, we could not
            # easily extract the data.
            for portnum in entry.get('_xcvrSlots', []):
                model = entry['_xcvrSlots'][portnum].get('modelName', '')
                if model:
                    status = 'present'
                else:
                    status = 'absent'
                newnentry = {
                    "name": f"port-{portnum}",  # Arista adds a /1 to ifname
                    "model": model,
                    "type": "xcvr",
                    "status": status,
                    "partNum": "",
                    "version": entry['_xcvrSlots'][portnum].get('hardwareRev',
                                                                ''),
                    "vendor": entry['_xcvrSlots'][portnum].get('mfgName',
                                                               '').lower(),
                    "serial": entry['_xcvrSlots'][portnum].get('serialNum',
                                                               ''),
                }
                new_data.append(newnentry)

            for fanNum in entry.get('_fanTraySlots', []):
                serial = entry['_fanTraySlots'][fanNum].get('serialNum', '')
                if serial == 'N/A':
                    serial = ''
                newentry = {
                    "name": f"fan-{fanNum}",
                    "type": "fan",
                    "serial": serial,
                    "model": entry['_fanTraySlots'][fanNum]
                    .get('name', ''),
                    "status": "present",
                    "vendor": entry['_fanTraySlots'][fanNum].get('vendor',
                                                                 'Arista'),
                    "version": ''
                }
                new_data.append(newentry)

            for powerNum in entry.get('_powerSupplySlots', []):
                newentry = {
                    "name": f"power-{powerNum}",
                    "type": "power",
                    "serial": entry['_powerSupplySlots'][powerNum]
                    .get('serialNum', ''),
                    "model": entry['_powerSupplySlots'][powerNum]
                    .get('name', ''),
                    "status": "present",
                    "vendor": entry['_powerSupplySlots'][powerNum].get(
                        'vendor', 'Arista'),
                    "version": ''  # Arista does not provide this
                }
                new_data.append(newentry)

            for fabricNum in entry.get('_cardSlots', []):
                model = entry['_cardSlots'][fabricNum].get('modelName', '')
                if model == "Not Inserted":
                    model = ''
                    status = 'absent'
                else:
                    status = 'present'
                ftype, num, _ = re.split(r'(\d)$', fabricNum)
                ftype = ftype.lower()
                newentry = {
                    "name": f'{ftype}-{num}',
                    "type": ftype,
                    "serial": entry['_cardSlots'][fabricNum]
                    .get('serialNum', ''),
                    "model": model.lower(),
                    "status": status,
                    "vendor": entry['_cardSlots'][fabricNum].get('vendor',
                                                                 'Arista'),
                    "version": entry['_cardSlots'][fabricNum].get(
                        'hardwareRev', ''),
                }
                new_data.append(newentry)

        return new_data

    def _clean_iosxr_data(self, processed_data, raw_data):
        pass

    def _clean_nxos_data(self, processed_data, _):

        for entry in processed_data:
            name = entry.get('name', '')
            entry['status'] = 'present'
            if name.find('Ethernet') != -1:
                entry['type'] = 'xcvr'
                if entry.get('_entryType', '') == '_textfsm':
                    status = entry.get('status', '')
                else:
                    status = entry.get('_sfp', '')
                if status.startswith("not "):
                    entry['status'] = 'absent'
                else:
                    entry['status'] = 'present'
            elif name.find('Chassis') != -1:
                entry['type'] = 'chassis'
                entry['name'] = name.lower()
                entry['model'] = ' '.join(entry['model'].split()[0:2])
            elif name.find('Slot') != -1:
                entry['type'] = 'linecard'
                entry['name'] = f'linecard-{name.split()[-1]}'
            elif name.find('Power Supply') != -1:
                entry['type'] = 'power'
                entry['name'] = f'power-{name.split()[-1]}'
                entry['model'] = ' '.join(entry['model'].split()[0:2])
            elif name.find('Fan') != -1:
                entry['type'] = 'fan'
                entry['name'] = f'fan-{name.split()[-1]}'
                entry['model'] = ' '.join(entry['model'].split()[0:2])

        return processed_data

    # pylint: disable=too-many-statements
    def _clean_junos_data(self, processed_data, _):
        new_data = []
        drop_indices = []

        # pylint: disable=too-many-nested-blocks
        for i, entry in enumerate(processed_data):
            if not entry['name']:
                drop_indices.append(i)
                continue

            name = entry.get('name', '').lower()
            if name == "midplane":
                entry['type'] = "midplane"
            elif name.startswith("fan"):
                entry['type'] = 'fan'
                if 'tray' in name:
                    entry['name'] = f'fan-{name.split()[0]}'
            elif name.startswith(('pdm', 'pem')):
                entry['type'] = 'power'
                name = name.replace(' ', '-')
            elif name.startswith('cb'):
                entry['type'] = 'mx-scb'
                name = name.replace(' ', '-')
            elif name.startswith('fpc'):
                fabid = name.split()[1]
                entry['type'] = 'linecard'
                name = f'linecard-{fabid}'
            elif name.startswith('routing'):
                entry['type'] = 'supervisor'
                name = name.replace(' ', '-')

            entry['name'] = name
            entry['status'] = 'present'
            entry['vendor'] = 'Juniper'
            submod = entry.get('_chassisSubMod', []) or []
            for ele in submod:
                subname = ele.get('name', [{}])[0].get('data', '')
                if not subname:
                    entry.pop('_chassisSubMod', None)
                    continue
                if not subname.startswith(('PIC', 'MIC')):
                    # Its another entry  away in this list
                    continue
                subid = subname.split()[1]
                port_substr = f'{fabid}/{subid}'
                if subname.startswith('MIC'):
                    nentry = {
                        'name': f'port-adapter-{fabid}/{subid}',
                        'vendor': 'Juniper',
                        'status': 'present',
                        'type': 'port-adapter',
                        'version': ele.get('version', [{}])[0].get('data', ''),
                        'serial': ele.get('serial-number', [{}])[0].get('data',
                                                                        ''),
                        'model': ele.get('model-number', [{}])[0].get('data',
                                                                      ''),
                        'partNum': ele.get('part-number', [{}])[0].get('data',
                                                                       '')
                    }
                    new_data.append(nentry)
                    picent = ele.get('chassis-sub-sub-module', [])
                    for pic in picent:
                        xcvr_ent = pic.get('chassis-sub-sub-sub-module', [])
                        for xent in xcvr_ent:
                            nentry = self._junos_create_xcvr_entry(
                                xent, port_substr)
                            if nentry:
                                new_data.append(nentry)
                else:
                    xcvr_ent = ele.get('chassis-sub-sub-module', [])
                    for xent in xcvr_ent:
                        nentry = self._junos_create_xcvr_entry(
                            xent, port_substr)
                        if nentry:
                            new_data.append(nentry)

            entry.pop('_chassisSubMod', None)

        processed_data = np.delete(processed_data, drop_indices).tolist()
        processed_data.extend(new_data)

        return processed_data

    def _junos_create_xcvr_entry(self, picent: dict, port_substr: str) -> dict:
        '''Create a Xcvr entry for a port in Junos'''
        xname = picent.get('name', [{}])[0].get('data', '')
        pid = xname.split()[1]
        partnum = picent.get('part-number', [{}])[0].get('data', '')
        if partnum == "NON-JNPR":
            vendor = 'unavailable'
        else:
            vendor = 'Juniper'
        nentry = {
            "name": f'port-{port_substr}/{pid}',
            "type": "xcvr",
            "status": "present",
            'vendor': vendor,
            "version": picent.get('version', [{}])[0].get('data', ''),
            "partType": picent.get('description', [{}])[0].get('data', ''),
            "partNum": partnum,
            "serial": picent.get('serial-number', [{}])[0].get(
                'data', ''),
        }

        return nentry

    def _clean_iosxe_data(self, processed_data, _):

        for entry in processed_data:
            name = entry['name']
            if name.endswith('Stack'):
                entry['type'] = 'chassis'
            elif 'StackPort' in name:
                entry['type'] = 'stackport'
                entry['partType'] = entry['descr']
            elif 'Power Supply' in name:
                entry['type'] = 'power'
            elif 'Uplink Module' in name:
                entry['type'] = 'uplink'
                entry['partType'] = entry['descr']
            elif name.startswith('Switch '):
                entry['type'] = 'stackswitch'

            else:
                entry['type'] = 'xcvr'
                entry['name'] = expand_ios_ifname(name)
                entry['partType'] = entry['descr']
            entry['status'] = 'present'

        return processed_data
