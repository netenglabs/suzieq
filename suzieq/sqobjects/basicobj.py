import logging
import typing
import pandas as pd

from suzieq.utils import load_sq_config, Schema, SchemaForTable
from suzieq.engines import get_sqengine


class SqContext(object):

    def __init__(self, engine, config_file=None):
        self.cfg = load_sq_config(config_file=config_file)

        self.schemas = Schema(self.cfg['schema-directory'])

        self.namespace = ''
        self.hostname = ''
        self.start_time = ''
        self.end_time = ''
        self.exec_time = ''
        self.engine = engine
        self.view = ''
        self.sort_fields = []


class SqObject(object):

    def __init__(self, engine_name: str = 'pandas',
                 hostname: typing.List[str] = [],
                 start_time: str = '', end_time: str = '',
                 view: str = '', namespace: typing.List[str] = [],
                 columns: typing.List[str] = ['default'],
                 context=None, table: str = '', config_file=None) -> None:

        if context is None:
            self.ctxt = SqContext(engine_name, config_file)
        else:
            self.ctxt = context
            if not self.ctxt:
                self.ctxt = SqContext(engine_name)

        self._cfg = self.ctxt.cfg
        self._schema = SchemaForTable(table, self.ctxt.schemas)
        self._table = table
        self._sort_fields = self._schema.key_fields()
        self._convert_args = {}

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
            view = self.ctxt.view

        if self.start_time and self.end_time and not view:
            self.view = 'all'
        else:
            self.view = view or 'latest'

        self.columns = columns

        if engine_name and engine_name != '':
            self.engine = get_sqengine(engine_name,
                                       self._table)(self._table, self)
        elif self.ctxt.engine:
            self.engine = get_sqengine(self.ctxt.engine,
                                       self._table)(self._table, self)

        if not self.engine:
            raise ValueError('Unknown analysis engine')

        self._addnl_filter = None
        self._addnl_fields = []
        self._valid_get_args = None
        self._valid_assert_args = None
        self._valid_arg_vals = None
        self._valid_find_args = None

    @property
    def all_schemas(self):
        return self.ctxt.schemas

    @property
    def schema(self):
        return self._schema

    @property
    def cfg(self):
        return self._cfg

    @property
    def table(self):
        return self._table

    def _check_input_for_valid_args(self, good_arg_list, **kwargs,):
        if not good_arg_list:
            return

        # add standard args that are always
        good_arg_list = good_arg_list + (['namespace', 'addnl_fields'])

        for arg in kwargs.keys():
            if arg not in good_arg_list:
                raise AttributeError(
                    f"argument {arg} not supported for this command")

    def _check_input_for_valid_vals(self, good_arg_val_list, **kwargs):
        '''Check if the input is valid for the arg, if possible'''

        if not good_arg_val_list:
            return

        for arg in kwargs.keys():
            if arg in good_arg_val_list:
                if kwargs[arg] not in good_arg_val_list[arg]:
                    raise AttributeError(
                        f"invalid value {kwargs[arg]} for argument {arg}")

    def validate_get_input(self, **kwargs):
        self._check_input_for_valid_args(
            self._valid_get_args + ['columns'], **kwargs)
        self._check_input_for_valid_vals(self._valid_arg_vals, **kwargs)

    def validate_assert_input(self, **kwargs):
        self._check_input_for_valid_args(self._valid_assert_args, **kwargs)

    def validate_columns(self, columns: typing.List[str]) -> bool:
        """Validate that the provided columns are valid for the table

        Args:
            columns (List[str]): list of columns

        Returns:
            bool: True if columns are valid
        Raises:
            ValueError: if columns are invalid
        """

        if columns == ['default'] or columns == ['*']:
            return True

        table_schema = SchemaForTable(self._table, self.all_schemas)
        invalid_columns = [x for x in columns if x not in table_schema.fields]
        if invalid_columns:
            raise ValueError(f"Invalid columns specified: {invalid_columns}")

    def get(self, **kwargs) -> pd.DataFrame:

        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        if self._addnl_filter:
            kwargs['add_filter'] = self._addnl_filter

        # This raises exceptions if it fails
        try:
            self.validate_get_input(**kwargs)
        except Exception as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df

        if 'columns' not in kwargs:
            kwargs['columns'] = self.columns or ['default']

        # This raises ValueError if it fails
        self.validate_columns(kwargs.get('columns', []))

        for k in self._convert_args:
            v = kwargs.get(k, None)
            if v:
                val = kwargs[k]
                newval = []
                if isinstance(val, list):
                    for ele in val:
                        ele = self._convert_args[k](ele)
                        newval.append(ele)
                    kwargs[k] = newval
                elif isinstance(val, str):
                    kwargs[k] = self._convert_args[k](val)

        return self.engine.get(**kwargs)

    def summarize(self, namespace=[], hostname=[],
                  query_str='') -> pd.DataFrame:
        if self.columns != ["default"]:
            self.summarize_df = pd.DataFrame(
                {'error': ['ERROR: You cannot specify columns with summarize']})
            return self.summarize_df
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        return self.engine.summarize(namespace=namespace, hostname=hostname,
                                     query_str=query_str)

    def unique(self, **kwargs) -> pd.DataFrame:
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        columns = kwargs.pop('columns', self.columns)
        column = columns[0]

        if columns is None or columns == ['default']:
            raise ValueError('Must specify columns with unique')

        if len(columns) > 1:
            raise ValueError('Specify a single column with unique')

        # This raises ValueError if it fails
        self.validate_columns(columns)
        return self.engine.unique(**kwargs, columns=columns)

    def aver(self, **kwargs):
        raise NotImplementedError

    def top(self, what: str = '', count: int = 5, reverse: bool = False,
            **kwargs) -> pd.DataFrame:
        """Get the list of top/bottom entries of "what" field"""

        columns = kwargs.get('columns', ['default'])
        # This raises ValueError if it fails
        self.validate_columns(columns)

        if not what:
            raise ValueError('Must specify what field to get top for')
        # if self._valid_get_args:
        #     self._valid_get_args += ['what', 'n', 'reverse']
        # This raises exceptions if it fails
        try:
            self.validate_get_input(**kwargs)
        except Exception as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df

        # This raises ValueError if it fails
        table_schema = SchemaForTable(self._table, self.all_schemas)
        if not self._field_exists(table_schema, what):
            raise ValueError(
                f"Field {what} does not exist in table {self.table}")

        columns = table_schema.get_display_fields(columns)

        ftype = table_schema.field(what).get('type', 'str')
        if ftype not in ['long', 'double', 'float', 'int', 'timestamp',
                         'timedelta64[s]']:
            return pd.DataFrame({'error': [f'{what} not numeric; top can be used with numeric fields only']})

        if what not in columns:
            self._addnl_fields.append(what)

        return self.engine.top(what=what, count=count, reverse=reverse, **kwargs)

    def describe(self, **kwargs):
        """Describes the fields for a given table"""

        table = kwargs.get('table', self.table)

        try:
            sch = SchemaForTable(table, self.all_schemas)
        except ValueError:
            sch = None
        if not sch:
            df = pd.DataFrame(
                {'error': [f'ERROR: incorrect table name {table}']})
            return df

        entries = [{'name': x['name'], 'type': x['type'],
                    'key': x.get('key', ''),
                    'display': x.get('display', ''),
                    'description': x.get('description', '')}
                   for x in sch.get_raw_schema()]
        df = pd.DataFrame.from_dict(entries).sort_values('name')

        return df

    def get_table_info(self, table: str, **kwargs) -> pd.DataFrame:
        """Get some basic stats about the table from the database

        Args:
            table (str): The table to get stats for

        Returns:
            pd.DataFrame: A dataframe with the stats
        """
        # This raises ValueError if it fails
        self.validate_columns(kwargs.get('columns', ['default']))

        return self.engine.get_table_info(table, **kwargs)

    def humanize_fields(self, df: pd.DataFrame, subset=None) -> pd.DataFrame:
        '''Humanize the fields for human consumption.

        Individual classes will implement the right transofmations. This
        routine is just a placeholder for all those with nothing to modify.
        '''
        return df

    def _field_exists(self, table_schema: SchemaForTable, field: str) -> bool:
        """Check if a field exists in the schema

        Args:
            table_schema (SchemaForTable): The schema for the table
            field (str): the field name we're checking for

        Returns:
            bool: True if the field exists, False otherwise
        """
        return table_schema.field(field)
