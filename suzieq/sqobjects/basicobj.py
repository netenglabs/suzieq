import typing
import pandas as pd

from suzieq.utils import load_sq_config, get_schemas
from suzieq.engines import get_sqengine


class SqContext(object):

    def __init__(self, engine):
        self.cfg = load_sq_config(validate=False)

        self.schemas = get_schemas(self.cfg['schema-directory'])

        self.namespace = ''
        self.hostname = ''
        self.start_time = ''
        self.end_time = ''
        self.exec_time = ''
        self.engine = 'pandas'
        self.system_df = {}
        self.sort_fields = []
        self.engine = get_sqengine(self.engine)
        if not self.engine:
            # We really should define our own error
            raise ValueError


class SqObject(object):

    def __init__(self, engine_name: str = '', hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = 'latest', namespace: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None, table: str = '') -> None:

        if context is None:
            self.ctxt = SqContext(engine_name)
        else:
            self.ctxt = context
            if not self.ctxt:
                self.ctxt = SqContext(engine_name)

        self._cfg = self.ctxt.cfg
        self._schemas = self.ctxt.schemas
        self._table = table
        self._sort_fields = []
        self._cat_fields = []
        self._ign_key_fields = []  # Used when keys != parquet partition cols

        if not namespace and self.ctxt.namespace:
            self.namespace = self.ctxt.namespace
        else:
            self.namespace = namespace
        if not hostname and self.ctxt.hostname:
            self.hostname = self.ctxt.hostname
        else:
            self.hostname = hostname

        if not start_time and self.ctxt.start_time:
            self.start_time = self.ctxt.start_time
        else:
            self.start_time = start_time

        if not end_time and self.ctxt.end_time:
            self.end_time = self.ctxt.end_time
        else:
            self.end_time = end_time

        if not view and self.ctxt.view:
            self.view = self.ctxt.view
        else:
            self.view = view
        self.columns = columns

        if engine_name and engine_name != '':
            self.engine = get_sqengine(engine_name)
        else:
            self.engine = self.ctxt.engine

        if self._table:
            self.engine_obj = self.engine.get_object(self._table, self)
        else:
            self.engine_obj = None

        self._addnl_filter = None

    @property
    def schemas(self):
        return self.ctxt.schemas

    @property
    def cfg(self):
        return self._cfg

    def get(self, **kwargs) -> pd.DataFrame:
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        if self._addnl_filter:
            kwargs['add_filter'] = self._addnl_filter

        if self._ign_key_fields:
            kwargs['ign_key'] = self._ign_key_fields

        return self.engine_obj.get(**kwargs)

    def summarize(self, namespace='') -> pd.DataFrame:
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.summarize(namespace=namespace)

    def unique(self, **kwargs) -> pd.DataFrame:
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine_obj.unique(**kwargs)

    def analyze(self, **kwargs):
        raise NotImplementedError

    def aver(self, **kwargs):
        raise NotImplementedError

    def top(self, **kwargs):
        raise NotImplementedError
