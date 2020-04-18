from suzieq.poller.services.service import Service
import re


class EvpnVniService(Service):
    """evpnVni service. Different class because output needs to be munged"""

    def clean_json_input(self, data):
        """FRR JSON data needs some work"""

        if data.get("devtype", None) == "cumulus":
            data['data'] = '[' + re.sub(r'}\n\n{\n', r'},\n\n{\n',
                                        data['data']) + ']'
            return data['data']

    def clean_data(self, processed_data, raw_data):

        if raw_data.get("devtype", None) == "cumulus":
            del_indices = []
            for i, entry in enumerate(processed_data):
                if entry['vni'] is None:
                    del_indices.append(i)

                for idx in del_indices:
                    del processed_data[idx]
        return super().clean_data(processed_data, raw_data)
