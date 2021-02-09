import logging
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

import pandas as pd


class SqDB(ABC):
    def __init__(self, cfg: dict, logger: logging.Logger):
        """Initialize the database

        :param cfg: dict, Suzieq config dictionary
        :param logger: logging.Logger, logger to use for logging
        :returns: Self
        :rtype: SqDB

        """
        self.cfg = cfg
        self.logger = logger or logging.getLogger()

    @abstractmethod
    def read(self, table_name: str, data_format: str,
             **kwargs) -> pd.DataFrame:
        """This is the routine that reads the DB and returns a pandas DF

        :param table_name: str, Name of the table to read data for
        :param data_format: str, Format the data's to be returned in,
                            (only pandas supported at this point)
        :returns: data in the form of a pandas dataframe
        :rtype: pd.DataFrame
        """
        raise NotImplementedError

    @abstractmethod
    def write(self, table_name: str, data_format: str,
              data, **kwargs) -> int:
        """Write the data supplied as a dataframe in the appropriate format

        :param cfg: Suzieq configuration
        :param table_name: str, Name of the table to write data to
        :param data: data to be written, usually pandas DF, but can be
                     engine specific (spark, dask etc.)
        :param data_format: str, Format the data's to be returned in,
                            (only pandas supported at this point)
        :returns: status of write
        :rtype: integer

        """
        raise NotImplementedError

    @abstractmethod
    def coalesce(self, tables: List[str] = None, period: str = '') -> None:
        """Coalesce the database files in specified folder.

        :param tables: List[str], List of specific tables to coalesce, empty for all
        : param period: str, period value to override what the configuration states
        :returns: Nothing

        """
        raise NotImplementedError


@dataclass
class SqCoalesceStats:
    service: str
    period: str                 # Coalescing period
    execTime: float            # execution time in secs
    fileCount: int          # number of files written
    recCount: int           # number of written records
    timestamp: int              # when this record was created
