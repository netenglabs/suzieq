import time
from nubia import command
from suzieq.cli.nubia_patch import argument

from suzieq.cli.sqcmds.command import SqTableCommand
from suzieq.sqobjects.namespace import NamespaceObj


@command("namespace", help="Summarize network-wide data")
class NamespaceCmd(SqTableCommand):
    """Overall network information such as namespaces present etc."""

    def __init__(
            self,
            engine: str = "",
            hostname: str = "",
            start_time: str = "",
            end_time: str = "",
            view: str = "",
            namespace: str = "",
            format: str = "",  # pylint: disable=redefined-builtin
            query_str: str = " ",
            columns: str = "default",
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
            query_str=query_str,
            sqobj=NamespaceObj,
        )

    @command("show", help="Show device information")
    @argument("model", description="model(s), space separated")
    @argument("os", description='NOS(es), space separated')
    @argument('vendor', description='Vendor(s), space separated')
    @argument('version', description='NOS version(s), space separated')
    # pylint: disable=arguments-differ
    def show(self, os: str = "", vendor: str = "", model: str = "",
             version: str = "") -> int:
        """Show network info
        """

        now = time.time()

        df = self._invoke_sqobj(self.sqobj.get,
                                namespace=self.namespace, os=os.split(),
                                vendor=vendor.split(), model=model.split(),
                                version=version, query_str=self.query_str,
                                hostname=self.hostname)

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._gen_output(df)
