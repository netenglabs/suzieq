from suzieq.sqobjects.basicobj import SqObject


class MroutesObj(SqObject):
    '''The object providing access to the mroutes table
    keys:
        - source
        - group
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
        super().__init__(table='mroutes', **kwargs)
        self._valid_get_args = ['namespace', 'hostname', 'columns', 'source', 'group', 'vrf', 'rpfInterface', 
                                'oifList', 'ipvers', 'rp', 'rpfneighbor']

