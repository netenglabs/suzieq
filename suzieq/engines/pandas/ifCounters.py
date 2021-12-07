from suzieq.engines.pandas.engineobj import SqPandasEngine


class IfcountersObj(SqPandasEngine):
    '''Backend class to handle ops on interface counters table with pandas'''

    @staticmethod
    def table_name():
        '''Table name'''
        return 'ifCounters'
