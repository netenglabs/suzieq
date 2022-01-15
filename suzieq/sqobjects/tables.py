from suzieq.sqobjects.basicobj import SqObject


class TablesObj(SqObject):
    '''The object providing access to the virtual table: tables'''

    def __init__(self, **kwargs) -> None:
        # We're passing any table name to get init to work
        super().__init__(table='tables', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns',
                                'query_str']
        self._unique_def_column = ['table']
