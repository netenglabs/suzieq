import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from suzieq.poller.worker.writers.output_worker_manager import \
    OutputWorkerManager
from suzieq.shared.context import SqContext
from suzieq.shared.schema import SchemaForTable
from suzieq.sqobjects.polledNodes import PolledNodesObj

logger = logging.getLogger(__name__)

SQ_OBJ_NAME = 'polledNodes'


class InventoryWriter:
    """InventoryWriter is the component in charge of writing and updating
    the nodes in the inventory
    """

    def __init__(self, sq_context: SqContext, outputs: List):
        """Initialize an InventoryWriter object

        Args:
            sq_context (SqContext): the SqContext containg the settings
            outputs (List): a list of the outputs where to write the inventory
        """
        self.sq_context = sq_context
        self._prev_inventory = None
        self._outputs = [o for o in outputs if o != 'gather']
        self._sq_obj = PolledNodesObj(context=sq_context)
        # Init the writers
        output_args = {
            'data_dir': self.sq_context.cfg.get('data-directory')
        }
        self.output_manager = OutputWorkerManager(self._outputs, output_args)
        self._output_queue = self.output_manager.output_queue

        # Get data schema
        schema = SchemaForTable(SQ_OBJ_NAME, self.sq_context.schemas)

        self._arrow_schema = schema.get_arrow_schema()
        self._partition_cols = schema.get_partition_columns()
        self._data_version = schema.version

    def write(self, new_inventory: Dict):
        """Store the inventory. This function gets the previous version of the
        inventory works out the different with the previous versions and writes
        only what changed.

        Args:
            new_inventory (Dict): the new version of the inventory
        """
        if self._prev_inventory is None:
            self._prev_inventory = self._read_inventory()
        inventory = [
            {
                'namespace': i['namespace'],
                'address': i['address'],
                'port': i['port']
            } for i in new_inventory.values()
        ]
        # Work out the differences with the previous inventory and write
        # only if something changed
        adds, dels = self._get_diff(inventory)
        if adds or dels:
            now = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
            for a in adds:
                a.update({
                    'sqvers': self._data_version,
                    'active': True,
                    'timestamp': now
                })
            for d in dels:
                d.update({
                    'sqvers': self._data_version,
                    'active': False,
                    'timestamp': now
                })
            to_write = adds
            to_write += dels
            self._write_inventory(to_write)
            self._prev_inventory = inventory

    def _read_inventory(self) -> List[Dict]:
        """Read and return the latest known version of the inventory

        Returns:
            List[Dict]: a list of the node in the latest known version of the
                inventory, containing [namespace, address, port]
        """
        prev = self._sq_obj.get().drop(columns=['timestamp'])
        return prev.to_dict('records')

    def _get_diff(self,
                  inventory: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Work out the differences between the new and the old version of the
        inventory

        Args:
            inventory (List[Dict]): the new version of the inventory containing
                for each node: namespace, address, port

        Returns:
            Tuple[List[Dict], List[Dict]]: return adds and dels of the new
                version of the inventory
        """
        adds = [a for a in inventory if a not in self._prev_inventory]
        dels = [r for r in self._prev_inventory if r not in inventory]

        return adds, dels

    def _write_inventory(self, records: List[Dict]):
        """Write the new version of the inventory

        Args:
            records (List[Dict]): the nodes added and removed from the
                inventory, each records has fields: sqvers, namespace, address
                and port
        """
        if records:
            self._output_queue.put_nowait(
                {
                    'records': records,
                    'topic': SQ_OBJ_NAME,
                    'schema': self._arrow_schema,
                    'partition_cols': self._partition_cols
                }
            )
