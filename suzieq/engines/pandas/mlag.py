from .engineobj import SqPandasEngine


class MlagObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'mlag'

    def summarize(self, **kwargs):
        """Summarize MLAG info"""

        self._summarize_on_add_field = [
            ('deviceCnt', 'hostname', 'nunique'),
            ('uniqueSystemIdCnt', 'systemId', 'nunique')
        ]

        self._summarize_on_add_with_query = [
            ('devicesWithfailedStateCnt', 'state != "active"', 'state'),
            ('devicesWithBackupInactiveCnt', 'state == "active"', 'backupActive')
        ]

        self._summarize_on_add_stat = [
            ('mlagNumDualPortsStat', 'state == "active"', 'mlagDualPortsCnt'),
            ('mlagNumSinglePortStat', 'state == "active"', 'mlagSinglePortsCnt'),
            ('mlagNumErrorPortStat', 'state == "active"', 'mlagErrorPortsCnt')
        ]

        return super().summarize(**kwargs)
