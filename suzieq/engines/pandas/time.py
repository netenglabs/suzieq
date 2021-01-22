from .engineobj import SqPandasEngine


class TimeObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'time'
