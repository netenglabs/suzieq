from suzieq.poller.services.service import Service
from suzieq.utils import expand_nxos_ifname


class InventoryService(Service):
    """Inventory service"""

    def _clean_eos_data(self, processed_data, raw_data):
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
                    "name": f"port-{portnum}",
                    "model": model,
                    "type": "xcvr",
                    "status": status,
                    "partNum": "",
                    "vendor": entry['_xcvrSlots'][portnum].get('mfgName', ''),
                    "serialNum": entry['_xcvrSlots'][portnum].get('serialNum',
                                                                  ''),
                }
                new_data.append(newnentry)

            for fanNum in entry.get('_fanTraySlots', []):
                newentry = {
                    "name": f"fan-{fanNum}",
                    "type": "fan",
                    "serialNum": entry['_fanTraySlots'][fanNum]
                    .get('serialNum', ''),
                    "model": entry['_fanTraySlots'][fanNum]
                    .get('name', ''),
                    "status": "present",
                }
                new_data.append(newentry)

            for powerNum in entry.get('_powerSupplySlots', []):
                newentry = {
                    "name": f"power-{powerNum}",
                    "type": "power",
                    "serialNum": entry['_powerSupplySlots'][powerNum]
                    .get('serialNum', ''),
                    "model": entry['_powerSupplySlots'][powerNum]
                    .get('name', ''),
                    "status": "present",
                }
                new_data.append(newentry)

        return new_data

    def _clean_iosxr_data(self, processed_data, raw_data):
        pass

    def _clean_nxos_data(self, processed_data, raw_data):
        pass

    def _clean_junos_data(self, processed_data, raw_data):
        pass

    def _clean_ios_data(self, processed_data, raw_data):
        pass
