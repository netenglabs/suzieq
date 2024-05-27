from typing import List

from ciscoconfparse import CiscoConfParse

from suzieq.engines.pandas.engineobj import SqPandasEngine


class DevconfigObj(SqPandasEngine):
    '''Backend class to handle manipulating device config table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'devconfig'

    def get(self, **kwargs):
        '''Retrieve the devconfig table info'''

        section = kwargs.pop('section', None)
        columns = kwargs.pop('columns', ['default'])
        query_str = kwargs.pop('query_str', '')

        df = super().get(columns=columns, **kwargs)
        if df.empty or 'error' in df.columns:
            return df

        if not section:
            if query_str:
                df = df.query(query_str).reset_index(drop=True)
            return df

        devdf = self._get_table_sqobj('device') \
            .get(columns=['namespace', 'hostname', 'os'], **kwargs)

        if devdf.empty or 'error' in devdf.columns:
            return df

        drop_indices: List[int] = []
        for index, row in enumerate(df.itertuples()):
            os = devdf.loc[(devdf['hostname'] == row.hostname) &
                           (devdf['namespace'] == row.namespace),
                           'os'].values[0]
            if os.startswith('junos') or os == 'panos':
                os = 'junos'
            elif os == 'nxos':
                os = 'nxos'
            else:
                os = 'ios'

            parsed_conf = CiscoConfParse(row.config.split('\n'), syntax=os)
            conf = '\n'.join(parsed_conf.find_all_children(section))
            if not conf:
                drop_indices.append(index)
            else:
                df.loc[index, 'config'] = conf

        if drop_indices:
            df = df.drop(index=drop_indices)

        if query_str:
            df = df.query(query_str).reset_index(drop=True)

        return df
