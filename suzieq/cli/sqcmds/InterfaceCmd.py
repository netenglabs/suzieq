import time

from nubia import command
import pandas as pd

from suzieq.cli.nubia_patch import argument
from suzieq.sqobjects import get_sqobject
from suzieq.cli.sqcmds.command import SqTableCommand


@command("interface", help="Act on Interface data")
@argument("ifname", description="interface name(s), space separated")
@argument("type", description="interface type(s), space separated")
@argument("vrf", description="VRF(s), space separated")
@argument("portmode", description="Portmode(s), space separated")
@argument("vlan", description="Vlan(s), space separated")
@argument("vrf", description="VRF(s), space separated")
@argument("state", description="interface state to qualify show",
          choices=["up", "down", "notConnected", "!up", "!down",
                   "!notConnected"])
@argument("mtu",
          description="MTU(s), space separated, can use <, >, <=, >=, !")
class InterfaceCmd(SqTableCommand):
    """Device interface information including MTU, Speed, IP address etc"""

    # pylint: disable=redefined-builtin
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
            query_str: str = ' ',
            ifname: str = '',
            state: str = '',
            type: str = '',
            vrf: str = '',
            mtu: str = '',
            portmode: str = '',
            vlan: str = '',
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
            sqobj=get_sqobject('interfaces')
        )
        self.lvars = {
            'ifname': ifname.split(),
            'state': state,
            'type': type.split(),
            'vrf': vrf.split(),
            'mtu': mtu.split(),
            'vlan': vlan.split(),
            'portmode': portmode.split(),
        }

    @command("assert")
    @argument(
        "what",
        description="What do you want to assert",
        choices=["mtu-value"],
    )
    @argument("value", description="Value to match against")
    @argument("result", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    @argument("ignore_missing_peer",
              description="Treat missing peer as passing assert check",
              choices=["True", "False"])
    def aver(self, what: str = "",
             value: str = '', result: str = 'all',
             ignore_missing_peer: str = "False"):
        """Assert aspects about the interface
        """

        now = time.time()

        if what == "mtu-value" and value == '':
            df = pd.DataFrame(
                {'error': ["Provide value to match MTU against"]}
            )
            return self._gen_output(df)

        elif not what:
            value = ''

        df = self._invoke_sqobj(self.sqobj.aver,
                                hostname=self.hostname,
                                namespace=self.namespace,
                                what=what,
                                columns=self._add_result_columns(self.columns),
                                matchval=value.split(),
                                result=result,
                                ignore_missing_peer=(
                                    ignore_missing_peer == "True"),
                                **self.lvars,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)
