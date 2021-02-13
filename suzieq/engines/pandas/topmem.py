from .engineobj import SqPandasEngine


class TopmemObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'topmem'
