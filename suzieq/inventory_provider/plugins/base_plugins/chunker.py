"""This module contains the base class for a Chunker.

Classes:
    Chunker: The duty of a chunker is to get the global inventory and split it
             in smaller chunks
"""
from abc import abstractmethod
from suzieq.shared.sq_plugin import SqPlugin


class Chunker(SqPlugin):
    """Abstract class for a Chunker
    """
    @abstractmethod
    def chunk(self, glob_inv, n_pollers, **addl_params):
        """Split the global inventory in <n_pollers> chunks

        Args:
            glob_inv ([type]): global inventory to split
            n_pollers ([type]): number of chunks
            addl_parameters ([type]): custom parameters that each Chunker
                                      plugin can define
        """
