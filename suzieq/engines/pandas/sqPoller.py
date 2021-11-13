from .engineobj import SqPandasEngine


class SqpollerObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'sqPoller'

    def get(self, **kwargs):

        status = kwargs.pop('status', '')
        poll_period_exceeded = kwargs.pop('pollExcdPeriodCount', '')
        columns = kwargs.pop('columns', [])

        drop_cols = []

        if status == "pass":
            add_filter = 'status == 0 or status == 200'
        elif status == "fail":
            add_filter = 'status != 0 and status != 200'
        else:
            add_filter = ''

        # We have to do this logic, otherwise the parquet filter will
        # pick the last entry which was not 0, for example, even if it
        # is not the latest, which is incorrect. Just like status=down
        if add_filter:
            add_prefix = ' and '
        else:
            add_prefix = ''

        if poll_period_exceeded:
            if poll_period_exceeded.startswith('!'):
                add_filter += f'{add_prefix}pollExcdPeriodCount != 0'
            else:
                add_filter += f'{add_prefix}pollExcdPeriodCount == 0'

        fields = self.schema.get_display_fields(columns)
        if status and 'status' not in fields:
            fields.append('status')
            drop_cols.append('status')

        if poll_period_exceeded and 'pollExcdPeriodCount' not in fields:
            fields.append('pollExcdPeriodCount')
            drop_cols.append('pollExcdPeriodCount')

        df = super().get(add_filter=add_filter, **kwargs)
        if not df.empty and add_filter:
            df = df.query(add_filter).reset_index(drop=True)

        if drop_cols:
            df = df.drop(drop_cols, axis=1, errors='ignore')

        return df

    def summarize(self, **kwargs):
        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('entriesCnt', 'hostname', 'count')
        ]

        self._summarize_on_add_list_or_count = [
            ('service', 'service'),
            ('status', 'status')
        ]

        self._summarize_on_add_stat = [
            ('pollExcdPeriodStat', '', 'pollExcdPeriodCount'),
        ]

        return super().summarize(**kwargs)
