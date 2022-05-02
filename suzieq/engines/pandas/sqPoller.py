from suzieq.engines.pandas.engineobj import SqPandasEngine


class SqpollerObj(SqPandasEngine):
    '''Backend class to handle manipulating sqpoller table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'sqPoller'

    def get(self, **kwargs):
        '''Retrieve sqpoller data for the given filters'''

        status = kwargs.pop('status', '')
        poll_period_exceeded = kwargs.pop('pollExcdPeriodCount', '')
        columns = kwargs.pop('columns', [])
        addnl_fields = kwargs.pop('addnl_fields', [])

        fields = self.schema.get_display_fields(columns)
        if status and 'status' not in fields:
            addnl_fields.append('status')

        self._add_active_to_fields(kwargs.get('view', self.iobj.view), fields,
                                   addnl_fields)

        if poll_period_exceeded and 'pollExcdPeriodCount' not in fields:
            addnl_fields.append('pollExcdPeriodCount')

        df = super().get(columns=fields, **kwargs)

        # Additionally filter by status or exceeded polling period. We need to
        # filter after getting the data because otherwise the parquet filter
        # will pick the last entry which was not 0, for example, even if it
        # is not the latest, which is incorrect. Just like status=down
        add_filter = ''
        if status == "pass":
            add_filter = 'status == 0 or status == 200'
        elif status == "fail":
            add_filter = 'status != 0 and status != 200'

        if add_filter:
            add_prefix = ' and '
        else:
            add_prefix = ''

        if poll_period_exceeded:
            if poll_period_exceeded.startswith('!'):
                add_filter += f'{add_prefix}pollExcdPeriodCount != 0'
            else:
                add_filter += f'{add_prefix}pollExcdPeriodCount == 0'

        if not df.empty and add_filter:
            df = df.query(add_filter).reset_index(drop=True)

        return df.reset_index(drop=True)[fields]

    def summarize(self, **kwargs):
        '''Summarize poller operational state data'''
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
