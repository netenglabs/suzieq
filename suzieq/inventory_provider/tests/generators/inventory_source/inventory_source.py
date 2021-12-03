"""This module contains the base class for inventorySource generators
"""
from abc import abstractmethod
from suzieq.inventory_provider.tests.generators.source_generator \
    import SourceGenerator


class InventorySourceGenerator(SourceGenerator):

    def generate(self):
        """This method generate both devices and their credentials
        calling self._generate_data() and self._generate_credentials()
        """        
        self._generate_data()
        self._generate_credentials()

    @abstractmethod
    def _generate_data(self):
        """This method generates random devices
        """
    @abstractmethod
    def _generate_credentials(self):
        """This method generate random credentials for
        generated devices
        """
