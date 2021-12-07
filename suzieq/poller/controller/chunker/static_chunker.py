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


class StaticChunker(Chunker):
    """StaticChunker splits the global inventory in chunks

    The StaticChunker supports policies for splitting:
    - random (default): splits the global inventory as is in chunks
    - namespace: splits the global inventory without splitting namespaces
    """

    def __init__(self, config_data: dict = None):

        self._split_policies_list = ["sequential", "namespace"]
        self._split_policies_fn = {}

        for pol_name in self._split_policies_list:
            fun = getattr(self, f"split_{pol_name}", None)
            if not fun or not callable(fun):
                raise RuntimeError(f"No split function for {pol_name}"
                                   " split policy")
            self._split_policies_fn[pol_name] = fun
        if config_data:
            self._split_pol = config_data \
                .get("split_pol", self._split_policies_list[0])
        else:
            self._split_pol = self._split_policies_list[0]

    def chunk(
        self,
        glob_inv: dict,
        n_pollers: int,
        **addl_params
    ) -> List[Dict]:

        split_pol = addl_params.pop("split_pol", self._split_pol)

        if addl_params:
            raise RuntimeError(f"Unused parameters {addl_params}")

        split_fun = self._split_policies_fn.get(split_pol, None)
        if not split_fun:
            raise AttributeError(f"Unknown split policy {split_pol}")

        return split_fun(glob_inv, n_pollers)

    def split_sequential(self, glob_inv: dict, n_pollers: int) -> List[Dict]:
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
        chunk_len = int(len(glob_inv)/n_pollers)

        # leftovers: if the number of devices in the inventory is not divisible
        #            by "n_pollers" and the inventory is splitted in
        #            "n_pollers" chunks of size "chunk_len", the result would
        #            be that the last inventory will contain more devices than
        #            the others.
        #            The "leftovoer" variable is used to distribute these
        #            additional devices to all the inventories

        leftovers = len(glob_inv) % n_pollers
        inv_chunks = []
        chunk_start = 0
        for _ in range(n_pollers):
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
            namespace = device.get("namespace", None)
            if namespace is None:
                raise AttributeError(f"{dev_name} doesn't have namespace set")
            if not inventory_namespaces.get(namespace, None):
                inventory_namespaces[namespace] = {}
            inventory_namespaces[namespace][dev_name] = device

        return get_chunked_inventory(inventory_namespaces, n_pollers)
