from .engineobj import SqPandasEngine


class DevconfigObj(SqPandasEngine):

    def __init__(self, baseobj):
        super().__init__(baseobj)

    @staticmethod
    def table_name():
        return 'devconfig'
