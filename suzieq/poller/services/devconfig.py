import re

from suzieq.poller.services.service import Service


class ConfigService(Service):
    """config service. Different class because minor munging of output"""

    def _common_data_cleaner(self, processed_data, raw_data):
        # The data we get is just a long string that is the config
        # No processing has been performed on the raw data. So processed_data
        # is empty

        output = raw_data[0].get('data', {})
        if isinstance(output, str):
            return []

        if 'output' in output.keys():
            data = output.get('output', "")
        else:
            data = raw_data[0].get('data', '')

        lines = data.splitlines()
        lines = list(filter(
            lambda x: not re.search(
                'Time|username|crypto|key-hash|encryption', x),
            lines))

        processed_data = [{'config': '\n'.join(lines)}]

        return processed_data

    def get_diff(self, old, new):
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
        elif newcfg and not oldcfg:
            adds = new
        else:
            hash_old = hash(oldcfg)
            hash_new = hash(newcfg)
            if hash_old != hash_new:
                adds = new

        return adds, dels
