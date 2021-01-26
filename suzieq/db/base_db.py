import pandas as pd
import logging
from abc import ABC, abstractmethod


class SqDB(ABC):
    def __init__(self):
        """Initialize the database

        :returns: Self
        :rtype: SqDB

        """
        self.cfg = None
        self.logger = logging.getLogger()

    @abstractmethod
    def get_table_df(self, cfg, schemas, **kwargs) -> pd.DataFrame:
        """This is the routine that reads the DB and returns a pandas DF

        :param cfg: dict, Suzieq config loaded
        :param schemas: dict, dictionary of table names to schemas
        :returns: data in the form of a pandas dataframe
        :rtype: pd.DataFrame
        """
        raise NotImplementedError
