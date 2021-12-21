"""
This module contains all the common logic of the
Suzieq poller inventory sources
"""
import abc
import asyncio
import logging
from collections import defaultdict
from typing import Callable, Coroutine, Dict, List

from suzieq.poller.worker.nodes.node import Node
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
                a task in the poller.
        """
        self._nodes = {}
        self._node_tasks = {}
        self.add_task_fn = add_task_fn

        self.connect_timeout = kwargs.pop('connect_timeout', 15)
        self.ssh_config_file = kwargs.pop('ssh_config_file', None)

    @property
    def nodes(self) -> Dict[str, Node]:
        """Get the current list of nodes in the inventory

        Returns:
            Dict[str, Node]: get a dictionary with the nodes in the inventory
                with format {namespace.hostname: Node}
        """
        return self._nodes

    @property
    def running_nodes(self) -> List[Coroutine]:
        """Get the the couroutines of the running nodes

        Returns:
            List[Coroutine]: a list containing the coroutines of the running
                nodes
        """
        return self._node_tasks

    async def build_inventory(self) -> Dict[str, Node]:
        """Retrieve the list of nodes to poll and instantiate
        all the Nodes objects in the retrieved inventory.

        Raises:
            SqPollerConfError: in case of wrong inventory configuration
            InventorySourceError: in case of error with the inventory source

        Returns:
            Dict[str, Node]: a list containing all the nodes in the inventory
        """

        inventory_list = await self._get_device_list()
        if not inventory_list:
            raise SqPollerConfError('The inventory source returned no hosts')

        # Initialize the nodes in the inventory
        self._nodes = await self._init_nodes(inventory_list)
        return self._nodes

    def get_node_callq(self) -> Dict[str, Dict]:
        """Get the dictionary allowing to send command query
        on the nodes

        Returns:
            Dict[str, Dict]: a dictionary having, for each 'namespace.hostname'
                the node hostname and the function allowing to call
                a query on the node.
        """
        node_callq = defaultdict(lambda: defaultdict(dict))

        node_callq.update({x: {'hostname': self._nodes[x].hostname,
                               'postq':    self._nodes[x].post_commands}
                           for x in self._nodes})

        return node_callq

    async def schedule_nodes_run(self):
        """Schedule the nodes tasks in the poller, so that they can
        start processing the command query passed to the nodes.

        This function should be called only once, if called more
        than once, it won't have any effect.
        """
        if not self._node_tasks:
            self._node_tasks = {node: self._nodes[node].run()
                                for node in self._nodes}
            await self.add_task_fn([t for t in self._node_tasks.values()])

    async def _init_nodes(self, inventory_list: List[Dict]) -> Dict[str, Node]:
        """Initialize the Node objects given the of credentials of the nodes.
        After this function is called, a connection with the nodes in the list
        is performed.

        Returns:
            Dict[str, Node]: a list containing the initialized Node objects
        """
        init_tasks = []
        nodes_list = {}

        for host in inventory_list:
            new_node = Node()
            # pylint: disable=protected-access
            init_tasks += [new_node._init(
                **host,
                connect_timeout=self.connect_timeout,
                ssh_config_file=self.ssh_config_file
            )]

        for n in asyncio.as_completed(init_tasks):
            newnode = await n
            if newnode.devtype is None:
                logger.error(
                    f'Unable to determine device type for '
                    f'{newnode.address}.{newnode.port}'
                )
            else:
                logger.info(f"Added node {newnode.hostname}:{newnode.port}")
                nodes_list.update({self.get_node_key(newnode): newnode})

        return nodes_list

    @abc.abstractmethod
    async def _get_device_list(self) -> List[Dict]:
        """Retrieve the devices credentials from the inventory
        source

        Raises:
            InventorySourceError: in case of error with the inventory source

        Returns:
            List[Dict]: the list of the credentials of the devices
                in the Suzieq native inventory file.
        """
        raise NotImplementedError

    @staticmethod
    def get_node_key(node: Node) -> str:
        """Given a node object it returns its ID key

        Args:
            node (Node): the node from which retrieving the key

        Returns:
            str: a string containing the ID key of the node
        """
        return f'{node.nsname}.{node.hostname}'
