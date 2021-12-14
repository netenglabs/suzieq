import typing
import pandas as pd

from suzieq.shared.utils import load_sq_config, humanize_timestamp
from suzieq.shared.schema import Schema, SchemaForTable
from suzieq.engines import get_sqengine
from suzieq.shared.sq_plugin import SqPlugin
from suzieq.shared.context import SqContext


class SqObject(SqPlugin):
    '''The base class for accessing the backend independent of the engine'''

    def __init__(self, engine_name: str = '',
                 hostname: typing.List[str] = None,
                 start_time: str = '', end_time: str = '',
                 view: str = '', namespace: typing.List[str] = None,
                 columns: typing.List[str] = None,
                 context=None, table: str = '', config_file=None) -> None:

        if not context:
            self.ctxt = SqContext(cfg=load_sq_config(validate=True,
                                                     config_file=config_file),
                                  engine=engine_name)
            self.ctxt.schemas = Schema(self.ctxt.cfg["schema-directory"])
        else:
            self.ctxt = context
            if not self.ctxt.cfg:
                self.ctxt.cfg = load_sq_config(validate=True,
                                               config_file=config_file)
                self.ctxt.schemas = Schema(self.ctxt.cfg["schema-directory"])
            if not self.ctxt.engine:
                self.ctxt.engine = engine_name

        self._cfg = self.ctxt.cfg
        self._schema = SchemaForTable(table, self.ctxt.schemas)
        self._table = table
        self._sort_fields = self._schema.key_fields()
        self._convert_args = {}

        self.namespace = namespace or self.ctxt.namespace or []
        self.hostname = hostname or self.ctxt.hostname or []
        self.start_time = start_time or self.ctxt.start_time
        self.end_time = end_time or self.ctxt.end_time

        view = view or self.ctxt.view

        if self.start_time and self.end_time and not view:
            self.view = 'all'
        else:
            self.view = view or 'latest'

        self.columns = columns or ['default']
        self._unique_def_column = ['hostname']

        if engine_name and engine_name != '':
            self.engine = get_sqengine(engine_name, self._table)(self)
        elif self.ctxt.engine:
            self.engine = get_sqengine(self.ctxt.engine, self._table)(self)

        if not self.engine:
            raise ValueError('Unknown analysis engine')

        self.summarize_df = pd.DataFrame()

        self._addnl_filter = self._addnl_fields = []
        self._valid_get_args = self._valid_assert_args = []
        self._valid_summarize_args = ['namespace', 'hostname', 'query_str']
        self._valid_arg_vals = self._valid_find_args = []

    @property
    def all_schemas(self):
        '''Return the set of all schemas of tables supported'''
        return self.ctxt.schemas

    @property
    def schema(self):
        '''Return table-specific schema'''
        return self._schema

    @property
    def cfg(self):
        '''Return general suzieq config'''
        return self._cfg

    @property
    def table(self):
        '''Return the table served by this object'''
        return self._table

    @property
    def addnl_fields(self):
        '''Return the additional fields field'''
        return self._addnl_fields

    @property
    def sort_fields(self):
        '''Return default list of fields to sort by'''
        return self._sort_fields

    def _check_input_for_valid_args(self, good_arg_list, **kwargs,):
        '''Check that the provided set of kwargs is valid for the table'''
        if not good_arg_list:
            return

        # add standard args that are always
        good_arg_list = good_arg_list + (['namespace', 'addnl_fields'])

        for arg in kwargs:
            if arg not in good_arg_list:
                raise AttributeError(
                    f"argument {arg} not supported for this command")

    def _check_input_for_valid_vals(self, good_arg_val_list, **kwargs):
        '''Check if the input is valid for the arg, if possible'''

        if not good_arg_val_list:
            return

        for arg, val in kwargs.items():
            if arg in good_arg_val_list:
                if val not in good_arg_val_list[arg]:
                    raise ValueError(
                        f"invalid value {val} for argument {arg}")

    def validate_get_input(self, **kwargs):
        '''Validate the values of the get function'''
        self._check_input_for_valid_args(
            self._valid_get_args + ['columns'], **kwargs)
        self._check_input_for_valid_vals(self._valid_arg_vals, **kwargs)

    def validate_assert_input(self, **kwargs):
        '''Validate the values of the assert function'''
        self._check_input_for_valid_args(self._valid_assert_args, **kwargs)

    def validate_summarize_input(self, **kwargs):
        '''Validate the values of the summarize function'''
        self._check_input_for_valid_args(self._valid_summarize_args, **kwargs)

    def validate_columns(self, columns: typing.List[str]) -> bool:
        """Validate that the provided columns are valid for the table

        Args:
            columns (List[str]): list of columns

        Returns:
            bool: True if columns are valid
        Raises:
            ValueError: if columns are invalid
        """

        if columns in [['default'], ['*']]:
            return True

        table_schema = SchemaForTable(self._table, self.all_schemas)
        invalid_columns = [x for x in columns if x not in table_schema.fields]
        if invalid_columns:
            raise ValueError(f"Invalid columns specified: {invalid_columns}")
        return True

    def get(self, **kwargs) -> pd.DataFrame:
        '''Return the data for this table given a set of attributes'''
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        if self._addnl_filter:
            kwargs['add_filter'] = self._addnl_filter

        # This raises exceptions if it fails
        try:
            self.validate_get_input(**kwargs)
        except (AttributeError, ValueError) as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df

        if 'columns' not in kwargs:
            kwargs['columns'] = self.columns or ['default']

        # This raises ValueError if it fails
        self.validate_columns(kwargs.get('columns', []))

        for k, v in self._convert_args.items():
            if v and k in kwargs:
                val = kwargs[k]
                newval = []
                if isinstance(val, list):
                    for ele in val:
                        ele = v(ele)
                        newval.append(ele)
                    kwargs[k] = newval
                elif isinstance(val, str):
                    kwargs[k] = v(val)

        return self.engine.get(**kwargs)

    def summarize(self, **kwargs) -> pd.DataFrame:
        '''Summarize the data from specific table'''
        if self.columns != ["default"]:
            self.summarize_df = pd.DataFrame(
                {'error':
                 ['ERROR: You cannot specify columns with summarize']})
            return self.summarize_df

        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        self.validate_summarize_input(**kwargs)

        return self.engine.summarize(**kwargs)

    def unique(self, **kwargs) -> pd.DataFrame:
        '''Identify unique values and value counts for a column in table'''
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        columns = kwargs.pop('columns', self.columns)

        if columns is None or columns == ['default']:
            columns = self._unique_def_column

        if len(columns) > 1 or columns == ['*']:
            raise ValueError('Specify a single column with unique')

        # This raises ValueError if it fails
        self.validate_columns(columns)
        self._check_input_for_valid_vals(self._valid_arg_vals, **kwargs)
        return self.engine.unique(**kwargs, columns=columns)

    def aver(self, **kwargs):
        '''Assert one or more checks on table'''
        if self._valid_assert_args:
            return self._assert_if_supported(**kwargs)

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
        except (ValueError, AttributeError) as error:
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
            return pd.DataFrame({'error':
                                 [f'{what} not numeric; top can be used with'
                                  f' numeric fields only']})

        if what not in columns:
            self._addnl_fields.append(what)

        return self.engine.top(what=what, count=count, reverse=reverse,
                               **kwargs)

    def describe(self, **kwargs):
        """Describes the fields for a given table"""

        table = kwargs.get('table', self.table)

        cols = kwargs.get('columns', ['default'])
        if cols not in [['default'], ['*']]:
            df = pd.DataFrame(
                {'error': ['ERROR: cannot specify column names for describe']})
            return df

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

    def humanize_fields(self, df: pd.DataFrame, _=None) -> pd.DataFrame:
        '''Humanize the fields for human consumption.

        Individual classes will implement the right transofmations. This
        routine is just a placeholder for all those with nothing to modify.
        '''
        if 'timestamp' in df.columns and not df.empty:
            df['timestamp'] = humanize_timestamp(df.timestamp,
                                                 self.cfg.get('analyzer', {})
                                                 .get('timezone', None))

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

    def _assert_if_supported(self, **kwargs):
        '''Common sqobj routine for a table that supports asserts

           Do not call this routine directly
        '''

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')
        try:
            self.validate_assert_input(**kwargs)
        except AttributeError as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df

        if self.columns in [['*'], ['default']]:
            req_cols = None
        else:
            req_cols = self.schema.get_display_fields(self.columns)
            if not req_cols:
                # Till we add a schema object for assert columns,
                # this will have to do
                req_cols = self.columns

        df = self.engine.aver(**kwargs)
        if not df.empty and req_cols:

            req_col_set = set(req_cols)
            got_col_set = set(df.columns)
            diff_cols = req_col_set - got_col_set
            if diff_cols:
                return pd.DataFrame(
                    {'error': [f'columns {list(diff_cols)} not in dataframe']})

            if 'assert' not in req_cols:
                req_cols.append('assert')

            df = df[req_cols]

        return df
