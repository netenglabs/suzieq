from .engineobj import SqPandasEngine


class IfcountersObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'ifCounters'
