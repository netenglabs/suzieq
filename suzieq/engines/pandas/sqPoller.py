from .engineobj import SqPandasEngine


class SqpollerObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'sqPoller'

    def get(self, **kwargs):

        status = kwargs.pop('status', '')

        if status == "pass":
            add_filter = 'status == 0 or status == 200'
        elif status == "fail":
            add_filter = 'status != 0 and status != 200'
        else:
            add_filter = ''

        return super().get(add_filter=add_filter, **kwargs)

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
