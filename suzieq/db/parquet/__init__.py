from .parquetdb import SqParquetDB
import logging


def get_sqdb(cfg: dict, logger: logging.Logger) -> SqParquetDB:
    """Return the parquet db engine for the appropriate table

    :param cfg: dict, Suzieq configuration dictionary
    :param logger: logging.Logger, logger to hook into for logging, can be None
    :returns: a parquet database engine to use for read/wr, other DB ops
    :rtype: SqParquetDB

    """
    return SqParquetDB(cfg, logger)


__all__ = [get_sqdb]
