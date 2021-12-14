from suzieq.sqobjects.basicobj import SqObject


class InventoryObj(SqObject):
    '''The object providing access to the inventory table'''

    def __init__(self, **kwargs):
        super().__init__(table='inventory', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'type',
                                'serial', 'vendor', 'status', 'model',
                                'query_str']
        self._unique_def_column = ['vendor']
