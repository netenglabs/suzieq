class SqEngine(object):
    def __init__(self):
        pass

    def get_table_df(self, cfg, schemas, **kwargs):
        raise NotImplementedError

    def get_object(self, objname: str):
        raise NotImplementedError


def get_sqengine(name: str = "pandas"):
    if name == 'pandas':
        from .pandas.engine import SqPandasEngine

        return SqPandasEngine()

    return None
