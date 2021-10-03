import time
import pandas as pd
from nubia import command, argument

from suzieq.cli.sqcmds.command import SqCommand, ArgHelpClass
from suzieq.sqobjects.path import PathObj


@command("path", help="build and act on path data")
class PathCmd(SqCommand):
    """Path trace information including overlay and underlay"""

    @argument("src", description="Source IP address, in quotes")
    @argument("dest", description="Destination IP address, in quotes")
    @argument("vrf", description="VRF to trace path in")
    def __init__(
        self,
        engine: str = "",
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        view: str = "",
        namespace: str = "",
        format: str = "",
        columns: str = "default",
        src: str = "",
        dest: str = "",
        vrf: str = "",
    ) -> None:
        super().__init__(
            engine=engine,
            hostname=hostname,
            start_time=start_time,
            end_time=end_time,
            view=view,
            namespace=namespace,
            columns=columns,
            format=format,
            sqobj=PathObj
        )
        self.src = src
        self.dest = dest
        self.vrf = vrf
        self._additional_help_vars = {
            # These are only required for args defined only in this class def
            'src': ArgHelpClass('Source IP address, in quotes'),
            'dest': ArgHelpClass('Destination IP address, in quotes'),
            'vrf': ArgHelpClass('VRF to trace path in')
        }

    @command("show")
    def show(self):
        """show paths between specified from source to target ip addresses"""
        # Get the default display field names
        if self.columns is None:
            return

        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        try:
            df = self.sqobj.get(
                hostname=self.hostname, columns=self.columns,
                namespace=self.namespace, source=self.src, dest=self.dest,
                vrf=self.vrf
            )
        except Exception as e:
            if len(e.args) > 1:
                df = e.args[1]  # The second arg if present is the path so far
                df['error'] = str(e.args[0])
            else:
                df = pd.DataFrame(
                    {'error': ['ERROR: {}'.format(str(e.args[0]))]})

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if not df.empty:
            return self._gen_output(df, sort=False)

    @command("summarize")
    def summarize(self):
        """Summarize paths between specified from source to target ip addresses"""
        # Get the default display field names
        if self.columns is None:
            return

        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        try:
            df = self.sqobj.summarize(
                hostname=self.hostname, namespace=self.namespace,
                source=self.src, dest=self.dest, vrf=self.vrf
            )
        except Exception as e:
            df = pd.DataFrame({'error': ['ERROR: {}'.format(str(e))]})

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if not df.empty:
            return self._gen_output(df)

    @command("unique")
    @argument("count", description="include count of times a value is seen",
              choices=['True'])
    def unique(self, count: str = 'False'):
        """Display unique values for specified field of a path"""
        # Get the default display field names
        if self.columns is None:
            return

        now = time.time()
        if self.columns != ["default"]:
            self.ctxt.sort_fields = None
        else:
            self.ctxt.sort_fields = []

        try:
            df = self.sqobj.unique(
                hostname=self.hostname, namespace=self.namespace,
                source=self.src, dest=self.dest, vrf=self.vrf,
                count=count
            )
        except Exception as e:
            df = pd.DataFrame({'error': ['ERROR: {}'.format(str(e))]})

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)
        if not df.empty:
            return self._gen_output(df)

    @command("top", help="find the top n values for a field")
    @argument("count", description="number of rows to return")
    @argument("what", description="integer field to get top values for")
    @argument("reverse", description="return bottom n values",
              choices=['True', 'False'])
    def top(self, count: int = 5, what: str = '', reverse: str = 'False',
            **kwargs) -> int:
        """Return the top n values for a field in path trace output

        Args:
            count (int, optional): The number of entries to return. Defaults to 5
            what (str, optional): Field name to use for largest/smallest val
            reverse (bool, optional): Reverse and return n smallest

        Returns:
            int: 0 or error code
        """
        now = time.time()

        df = self.sqobj.top(hostname=self.hostname,
                            namespace=self.namespace,
                            what=what, count=count, reverse=eval(reverse),
                            source=self.src, dest=self.dest, vrf=self.vrf,
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
