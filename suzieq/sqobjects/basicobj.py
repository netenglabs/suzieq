from typing import List
import re

import pandas as pd
from pandas.core.dtypes.dtypes import DatetimeTZDtype

from suzieq.shared.utils import (load_sq_config, humanize_timestamp,
                                 deprecated_table_function_warning)
from suzieq.shared.schema import Schema, SchemaForTable
from suzieq.engines import get_sqengine
from suzieq.shared.sq_plugin import SqPlugin
from suzieq.shared.context import SqContext


class SqObject(SqPlugin):
    '''The base class for accessing the backend independent of the engine'''

    def __init__(self, engine_name: str = '',
                 hostname: List[str] = None,
                 start_time: str = '', end_time: str = '',
                 view: str = '', namespace: List[str] = None,
                 columns: List[str] = None,
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

        # Init the engine
        engine_to_use = engine_name if engine_name else self.ctxt.engine
        self.engine = get_sqengine(engine_to_use, self._table)(self)

        self.summarize_df = pd.DataFrame()

        self._addnl_filter = []
        self._valid_get_args = self._valid_assert_args = []
        self._valid_arg_vals = self._valid_find_args = []
        self._valid_summarize_args = []

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
    def sort_fields(self):
        '''Return default list of fields to sort by'''
        return self._sort_fields

    @property
    def get_filter_fields(self):
        '''Return the set of fields in table that are specified as filters'''
        return [x for x in self._valid_get_args if x in self.schema.fields]

    @property
    def unique_default_column(self):
        '''Return the default unique column for this table'''
        return self._unique_def_column

    def _check_input_for_valid_args(self, good_arg_list, **kwargs,):
        '''Check that the provided set of kwargs is valid for the table'''
        if not good_arg_list:
            return

        # add standard args that are always
        good_arg_list = good_arg_list + (['namespace', 'ignore_warning'])

        for arg in kwargs:
            if arg not in good_arg_list:
                raise AttributeError(
                    f"argument {arg} not supported for this command")

    def _check_input_for_valid_vals(self, good_arg_val_list, **kwargs):
        '''Check if the input is valid for the arg, if possible'''

        fields = self.schema.fields
        for arg, val in kwargs.items():

            if arg not in fields:
                continue

            if arg not in good_arg_val_list:
                continue

            if not isinstance(val, list):
                chkval = [val]
            else:
                chkval = val
            for v in chkval:
                if v not in good_arg_val_list.get(arg, []):
                    raise ValueError(
                        f"invalid value {val} for argument {arg}")

    def validate_get_input(self, **kwargs):
        '''Validate the values of the get function'''
        fields = self.schema.fields
        for arg, val in kwargs.items():
            if arg not in fields or not val or not isinstance(val, list):
                # only if the value can be a split does a "> 100" become
                # a two element list instead of being a single element.
                # This is what the code below is fixing
                continue
            if (self.schema.field(arg).get('type', '') in ['int', 'long',
                                                           'float']):
                user_val = ' '.join(val)
                if user_val:
                    vals = re.split(r'(?<!<|>|=|!)\s+', user_val)
                    kwargs[arg] = vals

        self._check_input_for_valid_args(
            self._valid_get_args + ['columns'], **kwargs)
        self._check_input_for_valid_vals(self._valid_arg_vals, **kwargs)
        return kwargs

    def validate_assert_input(self, **kwargs):
        '''Validate the values of the assert function'''
        self._check_input_for_valid_args(self._valid_assert_args, **kwargs)

    def validate_summarize_input(self, **kwargs):
        '''Validate the values of the summarize function'''
        self._check_input_for_valid_args(self._valid_get_args, **kwargs)

    def validate_columns(self, columns: List[str]) -> bool:
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
        kwargs.pop('ignore_warning', None)
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        if self._addnl_filter:
            kwargs['add_filter'] = self._addnl_filter

        # This raises exceptions if it fails
        try:
            kwargs = self.validate_get_input(**kwargs)
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
        kwargs.pop('ignore_warning', None)
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
        kwargs.pop('ignore_warning', None)
        if not self._table:
            raise NotImplementedError

        if not self.ctxt.engine:
            raise AttributeError('No analysis engine specified')

        columns = kwargs.pop('columns', self.columns)
        count = kwargs.pop('count', 'False')

        if columns is None or columns == ['default']:
            columns = self._unique_def_column

        if len(columns) > 1 or columns == ['*']:
            raise ValueError('Specify a single column with unique')

        # This raises ValueError if it fails
        self.validate_columns(columns)
        self._check_input_for_valid_vals(self._valid_arg_vals, **kwargs)
        return self.engine.unique(**kwargs, count=str(count), columns=columns)

    def aver(self, **kwargs):
        '''Assert one or more checks on table'''
        kwargs.pop('ignore_warning', None)
        if self._valid_assert_args:
            return self._assert_if_supported(**kwargs)

        raise NotImplementedError

    def top(self, what: str = '', count: int = 5, reverse: bool = False,
            **kwargs) -> pd.DataFrame:
        """Get the list of top/bottom entries of "what" field"""
        kwargs.pop('ignore_warning', None)
        columns = kwargs.pop('columns', self.columns)
        # This raises ValueError if it fails
        self.validate_columns(columns)

        if not what:
            raise ValueError('Must specify what field to get top for')
        # if self._valid_get_args:
        #     self._valid_get_args += ['what', 'n', 'reverse']
        # This raises exceptions if it fails
        try:
            kwargs = self.validate_get_input(**kwargs)
        except (ValueError, AttributeError) as error:
            df = pd.DataFrame({'error': [f'{error}']})
            return df

        # This raises ValueError if it fails
        table_schema = SchemaForTable(self._table, self.all_schemas)
        if not self._field_exists(table_schema, what):
            raise ValueError(
                f"Field {what} does not exist in table {self.table}")

        ftype = table_schema.field(what).get('type', 'str')
        if ftype not in ['long', 'double', 'float', 'int', 'timestamp',
                         'timedelta64[s]']:
            return pd.DataFrame({'error':
                                 [f'{what} not numeric; top can be used with'
                                  f' numeric fields only']})

        return self.engine.top(what=what, count=int(count), reverse=reverse,
                               columns=columns, **kwargs)

    def describe(self, **kwargs):
        """Describes the fields for a given table"""
        kwargs.pop('ignore_warning', None)
        table = kwargs.get('table', self.table)

        if table in ['interface', 'route', 'mac', 'table']:
            # Handle singular/plural conversion
            table += 's'

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

        query_str = kwargs.get('query_str', '')
        if query_str:
            return df.query(query_str).reset_index(drop=True)

        return df

    def get_table_info(self, **kwargs) -> pd.DataFrame:
        """Get some basic stats about the table from the database

        Args:
            kwargs: keyword args passed by caller, varies depending on table

        Returns:
            pd.DataFrame: A dataframe with the stats
        """
        # This raises ValueError if it fails
        self.validate_columns(kwargs.get('columns', ['default']))

        return self.engine.get_table_info(**kwargs)

    def humanize_fields(self, df: pd.DataFrame, _=None) -> pd.DataFrame:
        '''Humanize the fields for human consumption.

        Individual classes will implement the right transofmations. This
        routine is just a placeholder for all those with nothing to modify.
        '''
        if 'timestamp' in df.columns and not df.empty:
            if isinstance(df.timestamp.dtype, DatetimeTZDtype):
                return df
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

        columns = kwargs.pop('columns', self.columns)

        if columns in [['*'], ['default']]:
            table_fields = None
        else:
            table_cols = [c for c in columns
                          if c not in ['result', 'assertReason']]
            table_fields = self.schema.get_display_fields(table_cols)
            if not table_fields:
                # Till we add a schema object for assert columns,
                # this will have to do
                table_fields = columns

        df = self.engine.aver(**kwargs)
        if table_fields:
            req_cols = (table_fields +
                        [c for c in columns if c not in table_fields])
            req_col_set = set(req_cols)
            got_col_set = set(df.columns)
            diff_cols = req_col_set - got_col_set
            if diff_cols:
                return pd.DataFrame(
                    {'error': [f'columns {list(diff_cols)} not in dataframe']})

            df = df[req_cols]

        return df

    def _run_deprecated_function(self, table: str, command: str,
                                 dep_command: str = None,
                                 ignore_warning: str = False,
                                 **kwargs):
        """ This function is in charge of running a deprecated function.
        First, it initializes a new sqobject using the same parameters used to
        initialize the sqobject calling this function. Then it checks if the
        command exists and run it setting the kwargs as arguments.

        Args:
            table (str): table to run the command
            command (str): command to run
            dep_command (str, optional): deprecated command.
            ignore_warning (str, optional): do not print the warning message.

        Raises:
            RuntimeError: unknown table or command
        """
        try:
            init_args = {
                'hostname': self.hostname,
                'start_time': self.start_time,
                'end_time': self.end_time,
                'view': self.view,
                'namespace': self.namespace,
                'columns': self.columns,
                'context': self.ctxt
            }
            if not dep_command:
                dep_command = command
            dep_table = self.table

            sqobjs = SqObject.get_plugins()
            if table not in sqobjs:
                raise RuntimeError(f'unknown table {table}')
            sqobj = sqobjs[table](**init_args)
            func = getattr(sqobj, command, None)
            if func is None or not callable(func):
                raise RuntimeError(f'unsupported function {command} '
                                   f'for {table}')
            if not ignore_warning:
                print(deprecated_table_function_warning(
                    dep_table, dep_command, table, command
                ))
            return func(**kwargs)
        except RuntimeError as e:
            return pd.DataFrame({'error': [str(e)]})
