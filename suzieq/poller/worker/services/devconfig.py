import re

from suzieq.poller.worker.services.service import Service


class ConfigService(Service):
    """config service. Different class because minor munging of output"""

    def _common_data_cleaner(self, processed_data, raw_data):
        # The data we get is just a long string that is the config
        # No processing has been performed on the raw data. So processed_data
        # is empty

        data = ''
        output = raw_data[0].get('data', {})
        if isinstance(output, list):
            output = output[0]

        if isinstance(output, dict):
            if 'output' in output.keys():
                data = output.get('output', "")
        else:
            data = output

        lines = data.splitlines()
        lines = list(filter(
            lambda x: not re.search(
                'Time|username|crypto|key-hash|encryption', x),
            lines))

        processed_data = [{'config': '\n'.join(lines)}]

        return processed_data

    def get_diff(self, old, new, add_all):
        """Compare string hashes for fast matches of config
        """

        adds = []
        dels = []

        if old:
            oldcfg = old[0].get('config', '')
        else:
            oldcfg = ''

        if new:
            newcfg = new[0].get('config', '')
        else:
            newcfg = ''

        if oldcfg and not newcfg:
            dels = new
        elif (newcfg and not oldcfg) or add_all:
            adds = new
        else:
            hash_old = hash(oldcfg)
            hash_new = hash(newcfg)
            if hash_old != hash_new:
                adds = new

        return adds, dels
