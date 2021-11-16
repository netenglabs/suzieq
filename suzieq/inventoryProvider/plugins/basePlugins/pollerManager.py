from abc import abstractmethod


class InventoryProvider:
    @abstractmethod
    def apply(inventory_chunks):
        '''
        Apply the inventory chunks to the pollers

        inventory_chunks: the portions of the global inventory to be passed
                          to the poller
        '''
        pass

    @abstractmethod
    def get_pollers_number(inventory):
        '''
        Get the number of pollers needed for querying the given inventory

        inventory: the inventory to be splitted across the poller instances
        '''

    @abstractmethod
    def run(inventory_chunks):
        pass
