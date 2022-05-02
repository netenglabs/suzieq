from suzieq.sqobjects.basicobj import SqObject


class MroutesObj(SqObject):
    '''The object providing access to the mroutes table
    keys:
        - source
        - group
        - vrf
    ignore-fields:
        - statusChangeTimestamp
    show-fields:
        - source
        - group
        - rpfInterface
        - oifList
        - vrf
        - ipvers
        - rp
        - rpfneighbor


    keys:
  - vlanName

show-fields:
  - vlanName
  - vlan
  - interfaces
    
    '''

    def __init__(self, **kwargs):
        super().__init__(table='routes', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'source', 'group', 'vrf', 'rpfInterface', 
                                'oifList', 'ipvers', 'rp', 'rpfneighbor']
        # self._valid_arg_vals = {'state': ['active', 'suspended', '']}
        # self._unique_def_column = ['source']
