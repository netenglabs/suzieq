from types import ModuleType

import streamlit as st
import suzieq.gui.SessionState as SessionState
import altair as alt
import pandas as pd

from suzieq.sqobjects import *
from suzieq.sqobjects.tables import TablesObj


def get_title():
    return 'XNA'


def get_df(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    columns = kwargs.pop('columns', ['default'])
    if columns == ['all']:
        columns = ['*']
    breakpoint()
    df = sqobject(view=view).get(columns=columns, **kwargs)
    if not (columns == ['*'] or columns == ['default']):
        return df[columns]
    return df


def run_summarize(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    df = sqobject(view=view).summarize(**kwargs)
    return df


def run_unique(sqobject, **kwargs):
    kwargs.pop('view', 'latest')
    df = sqobject().unique(**kwargs)
    if not df.empty:
        df.sort_values(by=['count'], inplace=True)
    return df


def run_assert(sqobject, **kwargs):
    kwargs.pop('view', 'latest')
    df = sqobject().aver(status="fail", **kwargs)
    if not df.empty:
        df.rename(columns={'assert': 'status'}, inplace=True, errors='ignore')
    return df


def build_sqobj_table() -> dict:
    '''Build available list of suzieq table objects'''

    sqobj_tables = {}
    module_list = globals()
    for key in module_list:
        if isinstance(module_list[key], ModuleType):
            if module_list[key].__package__ == 'suzieq.sqobjects':
                objlist = list(filter(lambda x: x.endswith('Obj'),
                                      dir(module_list[key])))
                for obj in objlist:
                    sqobj_tables[key] = getattr(module_list[key], obj)

    return sqobj_tables


def draw_sidebar_xna(state: SessionState, table_vals: list):
    '''Draw appropriate sidebar for the page'''

    state.xna_namespace = st.sidebar.text_input('Namespace',
                                                value=state.xna_namespace)
    state.xna_hostname = st.sidebar.text_input('Hostname',
                                               value=state.xna_hostname)
    if state.xna_table:
        tbl_idx = table_vals.index(state.xna_table)
    else:
        tbl_idx = 0
    state.xna_table = st.sidebar.selectbox(
        'Select Table to View', tuple(table_vals), index=tbl_idx)
    view_vals = ('latest', 'all')
    view_idx = 1 if state.xna_view == 'all' else 0
    state.xna_view = st.sidebar.radio("View of Data", view_vals,
                                      index=view_idx)
    fields = TablesObj().describe(table=state.xna_table)
    colist = sorted((filter(lambda x: x not in ['index', 'sqvers'],
                            fields.name.tolist())))
    columns = st.sidebar.multiselect('Pick columns',
                                     ['default', 'all'] + colist,
                                     default=state.xna_columns)
    if ('default' in columns or 'all' in columns) and len(columns) == 1:
        col_sel_val = True
    else:
        col_sel_val = False

    col_ok = st.sidebar.checkbox('Column Selection Done',
                                 value=col_sel_val)
    if not col_ok:
        columns = ['default']

    if not columns:
        columns = ['default']

    state.xna_columns = columns
    if state.xna_table in ['interfaces', 'ospf', 'bgp', 'evpnVni']:
        state.xna_assert_clicked = st.sidebar.checkbox(
            'Run Assert', value=state.xna_assert_clicked)
    else:
        state.xna_assert_clicked = False

    if not col_ok:
        st.stop()
    if ('default' in columns or 'all' in columns) and len(columns) != 1:
        st.error('Cannot select default/all with any other columns')
        st.stop()
    elif not columns:
        st.error('Columns cannot be empty')
        st.stop()

    state.xna_query = st.sidebar.text_input(
        'Filter table show results with pandas query', value=state.xna_query)
    st.sidebar.markdown(
        "[query syntax help](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.query.html)")

    if columns == 'all':
        columns = '*'

    col_expander = st.sidebar.beta_expander('Column Names', expanded=False)
    with col_expander:
        st.subheader(f'{state.xna_table} column names')
        st.table(TablesObj().describe(table=state.xna_table)
                 .query('name != "sqvers"')
                 .reset_index(drop=True).style)


def xna_run(state: SessionState):
    '''The main workhorse routine for the XNA page'''

    sqobjs = build_sqobj_table()
    table = draw_sidebar_xna(state, sorted(list(sqobjs.keys())))
