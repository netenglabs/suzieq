from .engineobj import SqPandasEngine


class TopcpuObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'topcpu'
