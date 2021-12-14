from suzieq.engines.pandas.engineobj import SqPandasEngine


class FsObj(SqPandasEngine):
    '''Backend class to handle manipulating filesystem table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'fs'
