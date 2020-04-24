import time
import pytz
import datetime
import pandas as pd
from nubia import command, argument, context


@argument(
    "engine",
    description="which analytical engine to use",
    choices=["pandas"],
)
@argument(
    "namespace", description="Space separated list of namespaces to qualify"
)
@argument("hostname", description="Space separated list of hostnames to qualify")
@argument(
    "start_time", description="Start of time window in YYYY-MM-dd HH:mm:SS pformat"
)
@argument(
    "end_time", description="End of time window in YYYY-MM-dd HH:mm:SS pformat"
)
@argument(
    "view",
    description="view all records or just the latest",
    choices=["all", "latest"],
)
@argument("columns", description="Space separated list of columns, * for all")
@argument(
    "format",
    description="select the pformat of the output",
    choices=["text", "json", "csv"],
)
class SqCommand:
    """Base Command Class for use with all verbs"""

    def __init__(
            self,
            engine: str = "",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "latest",
            namespace: str = "",
            format: str = "",
            columns: str = "default",
            sqobj=None,
    ) -> None:
        self.ctxt = context.get_context()
        self._cfg = self.ctxt.cfg
        self._schemas = self.ctxt.schemas

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

        if self.start_time and self.end_time:
            self.view = "all"
        else:
            self.view = view
        self.columns = columns.split()
        self.format = format or "text"
        self.json_print_handler = None

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

    def _gen_output(self, df: pd.DataFrame, json_orient: str = "records",
                    dont_strip_cols: bool = False):
        if df.columns.to_list() == ['error']:
            retcode = 1
            cols = df.columns
        else:
            retcode = 0
            if self.columns != ['default'] and self.columns != ['*']:
                cols = self.columns
            else:
                cols = df.columns

        if dont_strip_cols:
            cols = df.columns

        if self.format == 'json':
            if self.json_print_handler:
                print(df[cols].to_json(
                    default_handler=self.json_print_handler,
                    orient="records"))
            else:
                print(df[cols].to_json(orient=json_orient))
        elif self.format == 'csv':
            print(df[cols].to_csv())
        else:
            with pd.option_context('precision', 3,
                                   'display.max_rows', max(df.shape[0]+1, 64)):
                if df.empty:
                    print(df)
                else:
                    print(df[cols])

        return retcode

    def _assert_gen_output(self, df):
        if df.empty:
            result = 0
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

    def show(self, **kwargs):
        raise NotImplementedError

    def analyze(self, **kwargs):
        raise NotImplementedError

    def aver(self, **kwargs):
        raise NotImplementedError

    @command("summarize", help='produce a summarize of the data')
    def summarize(self, **kwargs):
        self._init_summarize()
        return self._post_summarize()

    def top(self, **kwargs):
        raise NotImplementedError

    @command("unique", help="find the list of unique items in a column")
    @argument("groupby", description="List of columns to group by")
    @argument("type", description="Unique per host or table entry",
              choices=['entry', 'host'])
    def unique(self, groupby='', type='entry', **kwargs):
        now = time.time()
        try:
            df = self.sqobj.unique(hostname=self.hostname,
                                   namespace=self.namespace,
                                   groupby=groupby, type=type,
                                   columns=self.columns)
        except Exception as e:
            df = pd.DataFrame({'error': ['ERROR: {}'.format(str(e))]})
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        return self._gen_output(df, dont_strip_cols=True)

    def _init_summarize(self):
        self.now = time.time()
        if self.columns != ["default"]:
            self.summarize_df = pd.DataFrame(
                {'error': ['ERROR: You cannot specify columns with summarize']})
            return self.summarize_df

        self.summarize_df = self.sqobj.summarize(
            namespace=self.namespace,
        )

    def _post_summarize(self):
        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - self.now)
        return self._gen_output(self.summarize_df)
