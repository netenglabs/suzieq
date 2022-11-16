import pytest

from tests.conftest import DATADIR, TABLES
from suzieq.sqobjects import get_sqobject


@ pytest.mark.schema
@ pytest.mark.parametrize('table',
                          [pytest.param(x,
                                        marks=getattr(pytest.mark, x))
                           for x in TABLES])
@ pytest.mark.parametrize('datadir', DATADIR)
@pytest.mark.parametrize('columns', [['*'], ['default']])
def test_schema_data_consistency(table, datadir, columns, get_table_data_cols):
    '''Test that all fields in dataframe and schema are consistent
        Only applies to show command for now
        It tests show columns=* is consistent with all fields in schema
        and that columns='default' matches all display fields in schema
    '''

    if table in ['path', 'tables', 'ospfIf', 'ospfNbr', 'topcpu',
                 'topmem', 'ifCounters', 'time']:
        return

    df = get_table_data_cols

    # We have to get rid of false assertions. A bunch of data sets don't
    # have valid values for one or more tables.
    skip_table_data = {'bgp': ['mixed'],
                       'ospf': ['vmx', 'basic_dual_bgp'],
                       'evpnVni': ['vmx', 'mixed', 'basic_dual_bgp'],
                       'mlag': ['vmx', 'junos', 'mixed'],
                       'devconfig': ['basic_dual_bgp'],
                       }
    if df.empty:
        if table in skip_table_data:
            for x in skip_table_data[table]:
                if x in datadir:
                    return
        elif table == "inventory" and 'vmx' not in datadir:
            return
        elif table == 'network':
            return

    assert not df.empty

    sqobj = get_sqobject(table)()
    all_cols = columns == ['*']
    schema_fld_set = set(sqobj.schema.sorted_display_fields(getall=all_cols))
    if table == 'topology':
        # By default, we don't pull arpnd
        schema_fld_set.remove('arpnd')
        schema_fld_set.remove('arpndBidir')

    df_fld_set = set(df.columns)
    assert not schema_fld_set.symmetric_difference(df_fld_set)
