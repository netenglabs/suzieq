
import time
import ast
import inspect
from io import StringIO
import shutil
from typing import List

import numpy as np
import pandas as pd
from nubia import command, context


from prompt_toolkit import prompt
from natsort import natsort_keygen
from colorama import Fore, Style

from termcolor import cprint, colored
from suzieq.cli.nubia_patch import argument
from suzieq.shared.sq_plugin import SqPlugin
from suzieq.shared.exceptions import UserQueryError
from suzieq.shared.utils import (DATA_FORMATS, SUPPORTED_ENGINES,
                                 deprecated_command_warning)


def colorize(x, color):
    '''Colorize string with the color provided'''
    return (f'{color}{Style.BRIGHT}{x}{Style.RESET_ALL}'
            if color else x)


@argument(
    "engine",
    description="Which analytical engine to use",
    choices=SUPPORTED_ENGINES,
)
@argument(
    "namespace", description="Namespace(s), space separated"
)
@argument("hostname",
          description="Hostname(s), space separated")
@argument(
    "start_time", description="Start of time window, try natural language spec"
)
@argument(
    "end_time", description="End of time window, try natural language spec "
)
@argument(
    "view",
    description="View all records or just the latest",
    choices=["all", "latest"],
)
@argument("columns", description="Space separated list of columns, * for all")
@argument(
    "format",
    description="Select the pformat of the output",
    choices=DATA_FORMATS,
)
@argument(
    "query_str",
    description="Trailing blank terminated pandas query format to "
    "further filter the output"
)
class SqCommand(SqPlugin):
    """Base Command Class for SuzieQ commands"""

    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "",
        namespace: str = "",
        format: str = "",  # pylint: disable=redefined-builtin
        columns: str = "default",
        query_str: str = " ",
        sqobj=None,
    ) -> None:
        self.ctxt = context.get_context().ctxt
        self._cfg = self.ctxt.cfg
        self._schemas = self.ctxt.schemas
        self.format = format or "text"
        self.columns = columns.split()
        self._json_print_handler = None
        self._additional_help_vars = {}

        if query_str.count('"') % 2 != 0:
            # This happens because nubia strips off the trailing quote
            # if not followed by a blank
            query_str += '"'
        elif query_str.count("'") % 2 != 0:
            # This happens because nubia strips off the trailing quote
            # if not followed by a blank
            query_str += "'"
        self.query_str = query_str.strip()

        if not isinstance(namespace, str):
            print('namespace must be a space separated list of strings')
            return
        if not isinstance(hostname, str):
            print('hostname must be a space separated list of strings')
            return
        if not isinstance(columns, str):
            print('columns must be a space separated list of strings')
            return

        if not namespace and self.ctxt.namespace:
            self.namespace = self.ctxt.namespace
        else:
            self.namespace = namespace.split()
        if not hostname and self.ctxt.hostname:
            self.hostname = self.ctxt.hostname
        else:
            self.hostname = hostname.split()

        if not start_time and self.ctxt.start_time:
            self.start_time = self.ctxt.start_time
        else:
            self.start_time = start_time

        if not end_time and self.ctxt.end_time:
            self.end_time = self.ctxt.end_time
        else:
            self.end_time = end_time

        self.view = view
        self.lvars = {}         # dict of var name and value for subclass

        if not sqobj:
            raise AttributeError('mandatory parameter sqobj missing')

        self.sqobj = sqobj(context=self.ctxt,
                           engine_name=engine,
                           hostname=self.hostname,
                           start_time=self.start_time,
                           end_time=self.end_time,
                           view=self.view,
                           namespace=self.namespace,
                           columns=self.columns)

    @property
    def cfg(self):
        '''Return the config'''
        return self._cfg

    @property
    def schemas(self):
        '''Return the schemas'''
        return self._schemas

    @ command("help", help="show help for a command")
    @ argument("command", description="command to show help for")
    # pylint: disable=redefined-outer-name
    def help(self, command: str = ''):
        """Show help for a command

        Args:
            command (str, optional): Name of the cmd. Defaults to 'show'.
        """
        if any(x for x in [self.namespace, self.hostname, self.view,
                           self.start_time, self.end_time, self.query_str]):
            print(Fore.RED + "Error: Only accepeted options is command")
            return 1
        if (self.columns != ["default"]) or (self.format != "text"):
            print(Fore.RED + "Error: Only accepted options is command")
            return 1

        if not command:
            mbrs = inspect.getmembers(self)
            verbs = {x[0]: x[1] for x in mbrs
                     if inspect.ismethod(x[1]) and not x[0].startswith('_')}
            print(f"{self.sqobj.table}: " + Fore.CYAN + f"{self.__doc__}" +
                  Style.RESET_ALL)
            verbs = {x: verbs[x] for x in verbs if x != 'get_plugins'}
            print("\nSupported verbs are: ")
            for verb in verbs:
                docstr = inspect.getdoc(verbs[verb])
                if docstr:
                    docstr = docstr.splitlines()[0]
                else:
                    docstr = ''
                verb = verb.replace('aver', 'assert')
                print(f" - {verb}: " + Fore.CYAN + f"{docstr}" +
                      Style.RESET_ALL)
        else:
            self._do_help(self.sqobj.table, command)

        return 0

    def _do_help(self, table: str, verb: str = 'show'):
        """Show help for a command

        Args:
            table (str): the table name
            verb (str, optional): the name of the command. Defaults to 'show'.
        """

        # Determine if the method is present
        if verb == 'assert':
            verb = 'aver'
        fn = inspect.getattr_static(self, verb, None)
        if not fn:
            print(f"No information about {table} {verb}")
            return

        help_dict = inspect.getattr_static(
            self, '__arguments_decorator_specs', None)

        args = list(filter(lambda x: not x.startswith('_') and
                           x not in ['ctxt', 'sqobj', 'lvars'],
                           self.__dict__))
        if self.lvars:
            args += list(self.lvars.keys())

        fnargs = inspect.getfullargspec(fn)
        if fnargs:
            args += list(filter(lambda x: x != 'self', fnargs.args))
            help_dict.update(inspect.getattr_static(
                fn, '__arguments_decorator_specs', {}))

        if not args:
            print(f"No argument information about {table} {verb}")
            return

        helpstr = inspect.getattr_static(self, '__arguments_decorator_specs',
                                         None)
        # Function help string
        docstr = inspect.getdoc(fn)
        if docstr:
            docstr = docstr.splitlines()[0]
        else:
            docstr = ''

        print(f"{table} {verb}: " + Fore.CYAN +
              f"{docstr}" + Style.RESET_ALL)
        if not args:
            print(f"No argument information about {table} {verb}")
            return

        print(Fore.YELLOW + '\nUse quotes when providing more than one value'
              + Style.RESET_ALL)
        print(Fore.YELLOW + '\nArguments:' + Style.RESET_ALL)

        for arg in sorted(args):
            if arg not in help_dict:
                helpstr = 'No description'
            else:
                helpstr = help_dict[arg].description

            print(f" - {arg}: " + colorize(helpstr, Fore.CYAN))

    def _pager_print(self, df: pd.DataFrame) -> None:
        '''To support paging'''

        if isinstance(df, pd.DataFrame) and df.index.dtype == 'int64':
            df.reset_index(drop=True, inplace=True)

        if self.ctxt.pager:
            screen_lines = (shutil.get_terminal_size((80, 20)).lines - 2)
            bufio = StringIO()

            print(df, file=bufio)
            lines = bufio.getvalue().split('\n')
            curline = 0
            total_lines = len(lines)
            while curline < total_lines:
                print('\n'.join(lines[curline:curline+screen_lines]))
                curline += screen_lines
                if curline < total_lines:
                    try:
                        _ = prompt('Hit <ENTER> to continue, <CTRL-D> to quit')
                    except EOFError:
                        break
        else:
            print(df)

    # pylint: disable=too-many-statements
    def _gen_output(self, df: pd.DataFrame, json_orient: str = "records",
                    dont_strip_cols: bool = False, sort: bool = True):

        if ('error' in df.columns or
                ('hopError' in df.columns and not df.empty
                 and (df.hopError != '').all())):
            retcode = 1
            max_colwidth = None
            cols = df.columns.tolist()
            is_error = True
        else:
            max_colwidth = self.ctxt.col_width
            retcode = 0
            if self.columns not in [['default'], ['*']]:
                cols = self.columns
            else:
                cols = df.columns.tolist()
            is_error = False

        max_rows = self.ctxt.max_rows
        all_columns = self.ctxt.all_columns

        if dont_strip_cols or not all(item in df.columns for item in cols):
            cols = df.columns.tolist()

        if self.format == 'json':
            if self._json_print_handler:
                print(df[cols].to_json(
                    default_handler=self._json_print_handler,
                    orient=json_orient))
            else:
                print(df[cols].to_json(orient=json_orient))
        elif self.format == 'csv':
            print(df[cols].to_csv())
        elif self.format == 'markdown':
            print(df[cols].to_markdown())
        elif (self.format == 'devconfig' and
              self.sqobj.table == "devconfig" and
              ('config' in df.columns)):
            for row in df.itertuples():
                self._pager_print(row.config)
        else:
            if 'active' in df.columns:
                df['active'] = np.where(df.active, '+', '-')
            if (not (self.view == "all" or self.columns == ['*'] or
                     (self.start_time and self.end_time) or dont_strip_cols
                     or 'timestamp' in self.columns)):
                if 'timestamp' in cols:
                    cols.remove('timestamp')
            with pd.option_context(
                    'precision', 3,
                    'display.max_colwidth', max_colwidth,
                    'display.max_rows', max_rows,
                    'display.expand_frame_repr', not all_columns):
                df = self.sqobj.humanize_fields(df)
                if df.empty:
                    print(df[cols])
                elif sort:
                    if is_error:
                        print(df[cols])
                    else:
                        if (((self.start_time and self.end_time) or
                             self.view == "all") and
                                'timestamp' in df.columns):
                            sort_fields = ['timestamp']
                        else:
                            sort_fields = [x for x in self.sqobj.sort_fields
                                           if x in df.columns and x in cols]
                        if sort_fields:
                            self._pager_print(
                                df[cols].sort_values(by=sort_fields,
                                                     key=natsort_keygen()))
                        else:
                            self._pager_print(df[cols])
                else:
                    self._pager_print(df[cols])

        return retcode

    def _assert_gen_output(self, df):
        if df.empty:
            result = 0
        elif df.columns.to_list() == ['error']:
            result = 1
        elif df.loc[df['result'] != "pass"].empty:
            result = 0
        else:
            result = -1

        self._gen_output(df)
        if self.format == 'text':
            if result == 0:
                print("Assert passed")
            else:
                print("Assert failed")
        return result

    def _invoke_sqobj(self, fn, **kwargs) -> pd.DataFrame:

        try:
            df = fn(**kwargs)
        except Exception as ex:  # pylint: disable=broad-except
            if isinstance(ex, UserQueryError):
                df = pd.DataFrame({'error': [f'ERROR: UserQueryError: {ex}']})
            else:
                if self.ctxt.debug:
                    raise Exception from ex
                df = pd.DataFrame({'error': [f'ERROR: {ex}']})

        return df

    @command("describe", help="describe the table and its fields")
    def describe(self):
        """Display the schema of the table

        Returns:
            [type]: 0 or error
        """
        now = time.time()

        for x in list(filter(lambda x: not x.startswith('_') and
                             x not in ['ctxt', 'sqobj', 'query_str',
                                       'format', 'columns', 'lvars'],
                             self.__dict__)):
            if getattr(self, x):
                print(Fore.RED + "Error: No arguments allowed for describe")
                return 1

        if any(x for x in self.lvars.values()):
            print(Fore.RED + "Error: No arguments allowed for describe")
            return 1

        df = self._invoke_sqobj(self.sqobj.describe,
                                hostname=self.hostname,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    def _print_depracation_command_warning(self,
                                           new_command: str,
                                           sub_command: str,
                                           dep_sub_command: str = None):
        """Print depracation command warning

        Args:
            new_command (str): command
            command (str): _description_
            dep_command (str, optional): _description_. Defaults to None.
        """
        if not dep_sub_command:
            dep_sub_command = sub_command
        dep_command = self.sqobj.table
        warning_msg = deprecated_command_warning(dep_command,
                                                 dep_sub_command,
                                                 new_command,
                                                 sub_command)
        cprint(colored(warning_msg, 'yellow'))

    def _add_result_columns(self, columns: List[str]) -> List[str]:
        """Append the 'result' column to the input columns if necessary.

        This function is used to always retrieve the 'result' column from the
        assertions which is necessary in the _assert_gen_output function.

        The 'result' column is not added if the input columns are '*' or
        'default' because the column will be already present

        Args:
            columns (List[str]): input columns

        Returns:
            List[str]: updated columns
        """
        return (
            columns
            if (columns in [['default'], ['*']] or
                'result' in columns)
            else columns + ['result']
        )


class SqTableCommand(SqCommand):
    """Base Command Class for table commands"""

    @command("summarize", help='produce a summarize of the data')
    def summarize(self, **kwargs):
        """Summarize relevant information about the table"""
        now = time.time()

        summarize_df = self._invoke_sqobj(
            self.sqobj.summarize, namespace=self.namespace,
            hostname=self.hostname, query_str=self.query_str,
            **self.lvars,
            **kwargs
        )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(summarize_df, json_orient='columns')

    @command("show")
    def show(self):
        """Show address info
        """
        # Get the default display field names
        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        df = self._invoke_sqobj(self.sqobj.get,
                                hostname=self.hostname,
                                columns=self.columns,
                                query_str=self.query_str,
                                namespace=self.namespace,
                                **self.lvars,
                                )
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("unique", help="find the list of unique items in a column")
    @argument("count", description="include count of times a value is seen",
              choices=['True'])
    def unique(self, count='', **kwargs):
        """Get unique values (and counts) associated with requested field"""
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.unique,
                                hostname=self.hostname,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                count=count,
                                **self.lvars,
                                **kwargs,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if 'error' in df.columns or df.empty:
            return self._gen_output(df)

        if not count:
            return self._gen_output(df.sort_values(by=[df.columns[0]]),
                                    dont_strip_cols=True)
        else:
            return self._gen_output(
                df.sort_values(by=['numRows', df.columns[0]]),
                dont_strip_cols=True)

    @ command("top", help="find the top n values for a field")
    @ argument("count", description="number of rows to return")
    @ argument("what", description="numeric field to get top values for")
    @ argument("reverse", description="return bottom n values",
               choices=['True', 'False'])
    def top(self, count: int = 5, what: str = '', reverse: str = 'False',
            **kwargs) -> int:
        """Return the top n values for a field in a table

        Args:
            count (int, optional): Number of entries to return. Defaults to 5
            what (str, optional): Field name to use for largest/smallest val
            reverse (bool, optional): Reverse and return n smallest

        Returns:
            int: 0 or error code
        """
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.top,
                                hostname=self.hostname,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                columns=self.columns,
                                what=what, count=count,
                                reverse=ast.literal_eval(reverse),
                                **self.lvars,
                                **kwargs,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if 'error' in df.columns:
            return self._gen_output(df)

        if not df.empty:
            df = self.sqobj.humanize_fields(df)
            return self._gen_output(df, dont_strip_cols=True, sort=False)
        else:
            return self._gen_output(df)

    @ command("help", help="show help for a command")
    @ argument("command", description="command to show help for",
               choices=['show', 'unique', 'summarize', 'assert', 'describe',
                        'top', "lpm"])
    # pylint: disable=redefined-outer-name
    def help(self, command: str = ''):
        return super().help(command)
