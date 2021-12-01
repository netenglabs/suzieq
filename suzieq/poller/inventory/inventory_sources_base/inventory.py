import abc
import asyncio
import logging
from collections import defaultdict
from typing import Callable, Dict, List

from suzieq.poller.nodes.node import Node
from suzieq.shared.exceptions import SqPollerConfError
from suzieq.shared.sq_plugin import SqPlugin

logger = logging.getLogger(__name__)


class Inventory(SqPlugin):
    """Inventory is the base class implemented by the
    inventory sources, providing the list of devices
    to poll.
    """

    def __init__(self, add_task_fn: Callable, **kwargs) -> None:
        """Instantiate the Inventory class

        Args:
            add_task_fn (Callable): the function to call to schedule
                a node task
        """
        self._nodes = {}
        self._node_tasks = {}
        self.add_task_fn = add_task_fn

        self.passphrase = kwargs.pop('passphrase', None)
        self.ssh_config_file = kwargs.pop('ssh_config_file', None)
        self.jump_host = kwargs.pop('jump_host', None)
        self.jump_host_key_file = kwargs.pop('jump_host_key_file', None)
        self.ignore_known_hosts = kwargs.pop('ignore_known_hosts', False)
        self.user_password = kwargs.pop('password', None)
        self.connect_timeout = kwargs.pop('connect_timeout', 15)

    @property
    def nodes(self):
        return self._nodes

    @property
    def running_nodes(self):
        return self._node_tasks

    async def build_inventory(self) -> List[Node]:
        """Retrieve the list of nodes to poll and instantiate
        all the Nodes objects in the retrieved inventory.

        Raises:
            SqPollerConfError: in case of wrong inventory configuration

        Returns:
            List[Node]: a list containing all the nodes in the inventory
        """

        inventory_list = self._get_device_list()
        if not inventory_list:
            raise SqPollerConfError('The inventory source returned no hosts')

        # Initialize the nodes in the inventory
        init_tasks = []
        for host in inventory_list:
            new_node = Node()
            init_tasks += [new_node._init(
                **host,
                passphrase=self.passphrase,
                ssh_config_file=self.ssh_config_file,
                jump_host=self.jump_host,
                jump_host_key_file=self.jump_host_key_file,
                connect_timeout=self.connect_timeout,
                ignore_known_hosts=self.ignore_known_hosts,
            )]

        for n in asyncio.as_completed(init_tasks):
            newnode = await n
            if newnode.devtype is None:
                logger.error(
                    "Unable to determine device type for {}:{}"
                    .format(newnode.address, newnode.port))
            else:
                logger.info(f"Added node {newnode.hostname}:{newnode.port}")

            self._nodes.update(
                {"{}.{}".format(newnode.nsname, newnode.hostname): newnode})

        return self._nodes

    def get_node_callq(self) -> Dict[str, Dict]:
        """Get the dictionary allowing to send command query
        on the nodes

        Returns:
            Dict[str, Dict]: a dictionary having, for each namespace.hostname,
                the node hostname and the function allowing to call
                a query on the node.
        """
        node_callq = defaultdict(lambda: defaultdict(dict))

        node_callq.update({x: {'hostname': self._nodes[x].hostname,
                               'postq':    self._nodes[x].post_commands}
                           for x in self._nodes})

        return node_callq

    async def schedule_nodes_run(self):
        """Schedule the nodes tasks, so that they can
        start processing the command query passed to the nodes.

        This function should be called only once, if called more
        than once, it won't have any effect.
        """
        if not self._node_tasks:
            self._node_tasks = {node: self._nodes[node].run()
                                for node in self._nodes}
            await self.add_task_fn(self._node_tasks.values())

    @abc.abstractmethod
    def _get_device_list(self):
        """Retrieve the devices list from the inventory source.
        """
        pass
