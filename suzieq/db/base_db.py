class SqDB(object):
    def __init__(self):
        pass

    def get_table_df(self, cfg, schemas, **kwargs):
        raise NotImplementedError

    def get_object(self, objname: str):
        raise NotImplementedError


def get_sqdb(name: str = "pandas"):
    if name == 'parquet':
        from .parquet import SqParquetDB

        return SqParquetDB()

    return None
