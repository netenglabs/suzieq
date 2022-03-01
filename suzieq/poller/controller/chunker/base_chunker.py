"""This module contains the base class for a Chunker.

Classes:
    Chunker: The duty of a chunker is to get the global inventory and split it
             in smaller chunks
"""
from abc import abstractmethod
from suzieq.poller.controller.base_controller_plugin import ControllerPlugin


class Chunker(ControllerPlugin):
    """Abstract class for a Chunker
    """

    @abstractmethod
    def chunk(self, glob_inv, n_chunks, **addl_params):
        """Split the global inventory in <n_chunks> chunks

        Args:
            glob_inv ([type]): global inventory to split
            n_chunks ([type]): number of chunks
            addl_parameters ([type]): custom parameters that each Chunker
                                      plugin can define
        """

    @classmethod
    def default_type(cls) -> str:
        return 'static'

    @classmethod
    def get_data_model(cls):
        """This is only temporary. In future release I will add chunker
        validation via pydantic
        """
        raise NotImplementedError
