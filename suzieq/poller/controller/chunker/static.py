"""StaticChunker module

This module contains a simple version a Chunker

Classes:
    StaticChunker: splits in a simple way the global inventory
                   in chunks

"""
from typing import Dict, List
import numpy as np
from suzieq.poller.controller.chunker.base_chunker \
    import Chunker
from suzieq.shared.exceptions import SqPollerConfError


class StaticChunker(Chunker):
    """StaticChunker splits the global inventory in chunks

    The StaticChunker supports policies for splitting:
    - sequential (default): splits the global inventory as is in chunks
    - namespace: splits the global inventory without splitting namespaces
    """

    def __init__(self, config_data: dict = None, validate: bool = True):
        super().__init__(config_data, validate)

        self.policies_list = ['sequential', 'namespace']
        self.policies_fn = {}

        for pol_name in self.policies_list:
            fun = getattr(self, f'split_{pol_name}', None)
            if not fun or not callable(fun):
                raise RuntimeError(f'Unknown {pol_name} policy')
            self.policies_fn[pol_name] = fun
        if config_data:
            policy = config_data \
                .get('policy', self.policies_list[0])
            if policy not in self.policies_list:
                raise SqPollerConfError(f'Unknown chunking policy {policy}')
            self.policy = policy
        else:
            self.policy = self.policies_list[0]

    @classmethod
    def get_data_model(cls):
        """This is only temporary. In future release I will add chunker
        validation via pydantic
        """
        raise NotImplementedError

    def chunk(self, glob_inv: dict, n_chunks: int, **kwargs) -> List[Dict]:

        policy = kwargs.pop('policy', self.policy)

        chunk_fun = self.policies_fn.get(policy, None)
        if not chunk_fun:
            raise SqPollerConfError(
                f'Unknown chunking function for policy {policy}')

        inv_chunks = [c for c in chunk_fun(glob_inv, n_chunks) if c]
        if len(inv_chunks) < n_chunks:
            if self.policy == 'sequential':
                raise SqPollerConfError(
                    'Not enough devices to split the inventory'
                    f'into {n_chunks} chunks'
                )
            if self.policy == 'namespace':
                raise SqPollerConfError(
                    'Not enough namespaces to split the inventory'
                    f'into {n_chunks} chunks'
                )
        return inv_chunks

    def split_sequential(self, glob_inv: dict, n_chunks: int) -> List[Dict]:
        """This function splits the global inventory following the
           same order of the global inventory. This function simply divides
           the global inventory as is "n_pollers" chunks without caring
           about, for example, splitting devices belonging to the same
           namespace

        Args:
            glob_inv (dict): the global inventory to split
            n_pollers (int): number of chunks to calculate

        Returns:
            List[Dict]: list of global_inventory chunks
        """
        chunk_len = int(len(glob_inv)/n_chunks)

        # leftovers: if the number of devices in the inventory is not divisible
        #            by "n_pollers" and the inventory is splitted in
        #            "n_pollers" chunks of size "chunk_len", the result would
        #            be that the last inventory will contain more devices than
        #            the others.
        #            The "leftover" variable is used to distribute these
        #            additional devices to all the inventories

        leftovers = len(glob_inv) % n_chunks
        inv_chunks = []
        chunk_start = 0
        for _ in range(n_chunks):
            if leftovers > 0:
                # leftovers must be divided between pollers
                inv_chunks.append(
                    dict(
                        list(glob_inv.items())
                        [chunk_start:chunk_start+chunk_len+1])
                )
                leftovers -= 1
                chunk_start += 1
            else:
                inv_chunks.append(
                    dict(
                        list(glob_inv.items())
                        [chunk_start:chunk_start+chunk_len])
                )
            chunk_start += chunk_len

        return inv_chunks

    def split_namespace(self, glob_inv: dict, n_pollers: int) -> List[Dict]:
        """split global inventory by namespace

        Args:
            glob_inv (dict): global inventory to split
            n_pollers (int): number of chunks to calculate

        Returns:
            List[Dict]: list of global_inventory chunks
        """

        def get_chunked_inventory(inventory_namespaces: dict, n_pollers: int):
            """
            This function splits the inventories trying to keep the same number
            of devices in each inventory chunk.

            namespaces_count contains the number of devices for each namespace
            chunk
            """
            namespaces_count = [0 for _ in range(n_pollers)]
            inventory_ns_chunks = [{} for _ in range(n_pollers)]

            for inv_ns_values in inventory_namespaces.values():
                min_index = np.argmin(namespaces_count)
                inventory_ns_chunks[min_index].update(inv_ns_values)
                namespaces_count[min_index] += len(inv_ns_values)

            return inventory_ns_chunks

        inventory_namespaces = {}

        for dev_name, device in glob_inv.items():
            namespace = device.get('namespace', None)
            if namespace is None:
                raise AttributeError(f"{dev_name} doesn't have namespace set")
            if not inventory_namespaces.get(namespace, None):
                inventory_namespaces[namespace] = {}
            inventory_namespaces[namespace][dev_name] = device

        return get_chunked_inventory(inventory_namespaces, n_pollers)
