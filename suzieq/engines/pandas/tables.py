from suzieq.engines.pandas.engineobj import SqPandasEngine


class TableObj(SqPandasEngine):

    @staticmethod
    def table_name():
        return 'tables'
