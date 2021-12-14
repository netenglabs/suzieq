from suzieq.engines.pandas.engineobj import SqPandasEngine


class TopcpuObj(SqPandasEngine):
    '''Backend class to handle manipulating topcpu table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'topcpu'
