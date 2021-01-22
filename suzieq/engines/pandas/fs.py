from .engineobj import SqPandasEngine


class FsObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'fs'
