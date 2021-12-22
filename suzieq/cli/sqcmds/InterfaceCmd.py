import time

from nubia import command

from suzieq.cli.nubia_patch import argument
from suzieq.sqobjects import get_sqobject
from suzieq.cli.sqcmds.command import SqCommand

import pandas as pd


@command("interface", help="Act on Interface data", aliases=['interfaces'])
@argument("ifname", description="interface name to qualify")
@argument("type", description="interface type to qualify")
@argument("vrf", description="filter interfaces matching VRFs")
@argument("state", description="interface state to qualify show",
          choices=["up", "down", "notConnected", "!up", "!down",
                   "!notConnected"])
@argument("mtu", description="filter interfaces with MTU")
class InterfaceCmd(SqCommand):
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
            mtu: str = ''
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
        }

    @command("assert")
    @argument(
        "what",
        description="What do you want to assert",
        choices=["mtu-value"],
    )
    @argument("value", description="Value to match against")
    @argument("status", description="Show only assert that matches this value",
              choices=["all", "fail", "pass"])
    @argument("ignore_missing_peer",
              description="Treat missing peer as passing assert check",
              choices=["True", "False"])
    def aver(self, what: str = "",
             value: str = '', status: str = 'all',
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
                                matchval=value.split(),
                                status=status,
                                ignore_missing_peer=(
                                    ignore_missing_peer == "True"),
                                **self.lvars,
                                )

        self.ctxt.exec_time = "{:5.4f}s".format(time.time() - now)

        return self._assert_gen_output(df)
