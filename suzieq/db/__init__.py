from suzieq.db.parquet import SqParquetDB

name = "sqdb"


def get_sqdb_engine(cfg: dict, table_name: str):
    """Return the appropriate DB reader for the given table

    This function is dumb right now. Will get smarter as we add support for 
    more database readers.

    :param cfg: dict, Suzieq loaded config
    :param table_name: str, Name of the table you want to read
    :returns: the class that is the reader for this object
    :rtype: 
    """
    return SqParquetDB()


__all__ = [get_sqdb_engine]
