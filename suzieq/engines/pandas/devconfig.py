from suzieq.engines.pandas.engineobj import SqPandasEngine


class DevconfigObj(SqPandasEngine):
    '''Backend class to handle manipulating device config table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'devconfig'
