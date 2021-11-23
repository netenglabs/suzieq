
import time
import ast
from dataclasses import dataclass
import inspect

import pandas as pd
from nubia import command, argument, context
from io import StringIO
import shutil
from prompt_toolkit import prompt
from natsort import natsort_keygen
from colorama import Fore, Style

from suzieq.exceptions import UserQueryError


@dataclass
class ArgHelpClass(object):
    '''Class holding description and other params to display help
    This class exists to simplify displaying help for vars that we
    cannot access via the classargspec var
    '''
    description: str = ''


@argument(
    "engine",
    description="Which analytical engine to use",
    choices=["pandas"],
)
@argument(
    "namespace", description="Space separated list of namespaces to qualify"
)
@argument("hostname",
          description="Space separated list of hostnames to qualify")
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
    choices=["text", "json", "csv", "markdown"],
)
@argument(
    "query_str",
    description=("Trailing blank terminated pandas query format to "
                 "further filter the output",)
)
class SqCommand:
    """Base Command Class for use with all verbs"""

    def __init__(
            self,
            engine: str = "pandas",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "",
            namespace: str = "",
            format: str = "",
            columns: str = "default",
            query_str: str = " ",
            sqobj=None,
    ) -> None:
        self.ctxt = context.get_context()
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

        if not sqobj:
            raise AttributeError('mandatory parameter sqobj missing')

        self.sqobj = sqobj(context=self.ctxt,
                           hostname=self.hostname,
                           start_time=self.start_time,
                           end_time=self.end_time,
                           view=self.view,
                           namespace=self.namespace,
                           columns=self.columns)

    @property
    def cfg(self):
        return self._cfg

    @property
    def schemas(self):
        return self._schemas

    @command("summarize", help='produce a summarize of the data')
    def summarize(self):
        """Summarize relevant information about the table"""
        if not self._init_summarize():
            return self._gen_output(self.summarize_df)

        return self._post_summarize()

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
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if 'error' in df.columns:
            return self._gen_output(df)

        if df.empty:
            return df

        if not count:
            return self._gen_output(df.sort_values(by=[df.columns[0]]),
                                    dont_strip_cols=True)
        else:
            return self._gen_output(
                df.sort_values(by=['numRows', df.columns[0]]),
                dont_strip_cols=True)

    @command("describe", help="describe the table and its fields")
    def describe(self):
        """Display the schema of the table

        Returns:
            [type]: 0 or error
        """
        now = time.time()

        df = self._invoke_sqobj(self.sqobj.describe,
                                hostname=self.hostname,
                                namespace=self.namespace,
                                query_str=self.query_str,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df)

    @command("top", help="find the top n values for a field")
    @argument("count", description="number of rows to return")
    @argument("what", description="integer field to get top values for")
    @argument("reverse", description="return bottom n values",
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
                                what=what, count=count,
                                reverse=ast.literal_eval(reverse),
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if 'error' in df.columns:
            return self._gen_output(df)

        if not df.empty:
            df = self.sqobj.humanize_fields(df)
            return self._gen_output(df.sort_values(by=[what], ascending=False),
                                    dont_strip_cols=True, sort=False)
        else:
            return self._gen_output(df)

    @command("help", help="show help for a command")
    @argument("command", description="command to show help for",
              choices=['show', 'unique', 'summarize', 'assert', 'describe',
                       'top', "find", "lpm"])
    def help(self, command: str = ''):
        """Show help for a command

        Args:
            command (str, optional): Name of the command. Defaults to 'show'.
        """
        if any(x for x in [self.namespace, self.hostname, self.view,
                           self.start_time, self.end_time, self.query_str]):
            print(Fore.RED + "Error: Only accepeted options is command")
            return
        if (self.columns != ["default"]) or (self.format != "text"):
            print(Fore.RED + "Error: Only accepeted options is command")
            return

        if not command:
            mbrs = inspect.getmembers(self)
            verbs = {x[0]: x[1] for x in mbrs
                     if inspect.ismethod(x[1]) and not x[0].startswith('_')}
            print(f"{self.sqobj.table}: " + Fore.CYAN + f"{self.__doc__}" +
                  Style.RESET_ALL)
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

    def _do_help(self, table: str, verb: str = 'show'):
        """Show help for a command

        Args:
            table (str): the table name
            verb (str, optional): the name of the command. Defaults to 'show'.
        """

        mbrs = inspect.getmembers(self)
        classargspec = [x[1] for x in mbrs
                        if x[0] == '__arguments_decorator_specs']
        if classargspec:
            classargspec = classargspec[0]
        verbs = [x[0] for x in mbrs
                 if inspect.ismethod(x[1]) and not x[0].startswith('_')]
        fnlist = {x[0]: x[1] for x in mbrs
                  if x[0] in verbs}
        newverb = verb.replace('assert', 'aver')
        if newverb in fnlist:
            fnargs = []

            fnmbrs = inspect.getmembers(fnlist[newverb])
            for elem in fnmbrs:
                if elem[0] == "__arguments_decorator_specs":
                    fnargs = elem[1]
                    break

            docstr = inspect.getdoc(fnlist[newverb])
            if docstr:
                docstr = docstr.splitlines()[0]
            else:
                docstr = ''
            print(f"{table} {verb}: " + Fore.CYAN +
                  f"{docstr}" + Style.RESET_ALL)
            print(Fore.YELLOW + '\nArguments:' + Style.RESET_ALL)
            if fnargs:
                classargspec.update(fnargs)
            classargspec.update(self._additional_help_vars)
            for arg in sorted(classargspec):
                print(f" - {arg}: " + Fore.CYAN +
                      f"{classargspec[arg].description}" + Style.RESET_ALL)
        else:
            print(f"No information about {table} {verb}")

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

        return

    def _gen_output(self, df: pd.DataFrame, json_orient: str = "records",
                    dont_strip_cols: bool = False, sort: bool = True):

        if 'error' in df.columns:
            retcode = 1
            max_colwidth = None
            cols = df.columns
            is_error = True
        else:
            max_colwidth = self.ctxt.col_width
            retcode = 0
            if self.columns != ['default'] and self.columns != ['*']:
                cols = self.columns
            else:
                cols = df.columns
            is_error = False

        if dont_strip_cols or not all(item in df.columns for item in cols):
            cols = df.columns

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
              'error' not in df.columns):
            for row in df.itertuples():
                self._pager_print(row.config)
        else:
            with pd.option_context('precision', 3,
                                   'display.max_colwidth', max_colwidth,
                                   'display.max_rows', 256):
                if df.empty:
                    print(df)
                elif sort:
                    if is_error:
                        print(df[cols])
                    else:
                        sort_fields = [x for x in self.sqobj._sort_fields
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
        elif df.loc[df['assert'] != "pass"].empty:
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
        except Exception as ex:
            if isinstance(ex, UserQueryError):
                df = pd.DataFrame({'error': [f'ERROR: UserQueryError: {ex}']})
            else:
                df = pd.DataFrame({'error': [f'ERROR: {ex}']})

        return df

    def _init_summarize(self):
        self.now = time.time()

        self.summarize_df = self._invoke_sqobj(
            self.sqobj.summarize, namespace=self.namespace,
            hostname=self.hostname, query_str=self.query_str
        )
        return 'error' not in self.summarize_df

    def _post_summarize(self):
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - self.now)
        return self._gen_output(self.summarize_df, json_orient='columns')
