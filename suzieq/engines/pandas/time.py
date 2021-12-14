from suzieq.engines.pandas.engineobj import SqPandasEngine


class TimeObj(SqPandasEngine):
    '''Backend class to handle manipulating time table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'time'
