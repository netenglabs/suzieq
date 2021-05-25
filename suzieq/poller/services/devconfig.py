from suzieq.poller.services.service import Service


class ConfigService(Service):
    """config service. Different class because minor munging of output"""

    def _common_data_cleaner(self, processed_data, raw_data):
        # The data we get is just a long string that is the config
        # No processing has been performed on the raw data. So processed_data
        # is empty

        if 'output' in raw_data[0].get('data', {}):
            data = raw_data[0].get('data', {'output': {}}).get('output', "")
        else:
            data = raw_data[0].get('data', '')

        nomatch = True
        if data:
            lines = data.splitlines()
            for lindx, line in enumerate(lines):
                if line.startswith('!Time'):
                    nomatch = False
                    break

        if nomatch:
            processed_data = [{'config': data}]
        else:
            processed_data = [
                {'config': '\n'.join(lines[:lindx] + lines[lindx+1:])}]

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
