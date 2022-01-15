from suzieq.engines.pandas.engineobj import SqPandasEngine


class TopmemObj(SqPandasEngine):
    '''Backend class to handle manipulating topmem table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'topmem'
