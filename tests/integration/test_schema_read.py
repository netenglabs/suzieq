import pytest
from _pytest.mark.structures import Mark, MarkDecorator

from tests.conftest import DATADIR
from suzieq.sqobjects import get_tables, get_sqobject


@ pytest.mark.schema
@ pytest.mark.parametrize('table',
                          [pytest.param(x,
                                        marks=MarkDecorator(Mark(x, [], {})))
                           for x in get_tables()])
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
                       'ospf': ['vmx'],
                       'evpnVni': ['vmx', 'mixed'],
                       'mlag': ['vmx', 'junos', 'mixed'],
                       }
    if df.empty:
        if table in skip_table_data:
            for x in skip_table_data[table]:
                if x in datadir:
                    return
        elif table == "inventory" and 'vmx' not in datadir:
            return

    assert not df.empty

    sqobj = get_sqobject(table)()
    if columns == ['*']:
        schema_fld_set = set(sqobj.schema.fields)
        schema_fld_set.remove('sqvers')
        if table == 'bgp':
            schema_fld_set.remove('origPeer')
        elif table == "macs":
            schema_fld_set.remove('mackey')
    else:
        schema_fld_set = set(sqobj.schema.sorted_display_fields())

    df_fld_set = set(df.columns)
    assert not schema_fld_set.symmetric_difference(df_fld_set)
