from types import ModuleType

import streamlit as st
import suzieq.gui.SessionState as SessionState
import altair as alt
import pandas as pd

from suzieq.sqobjects import *
from suzieq.sqobjects.tables import TablesObj
from suzieq.gui.guiutils import sq_gui_style


def get_title():
    return 'XNA'


@st.cache(ttl=90, allow_output_mutation=True)
def xna_get_df(sqobject, **kwargs):
    table = kwargs.pop('_table', '')
    view = kwargs.pop('view', 'latest')
    columns = kwargs.pop('columns', ['default'])
    if columns == ['all']:
        columns = ['*']
    df = sqobject(view=view).get(columns=columns, **kwargs)
    if not df.empty:
        if table == 'address':
            if 'ipAddressList' in df.columns:
                df = df.explode('ipAddressList').fillna('')
            if 'ip6AddressList' in df.columns:
                df = df.explode('ip6AddressList').fillna('')
    if not (columns == ['*'] or columns == ['default']):
        return df[columns].reset_index()
    return df.reset_index()


@ st.cache(ttl=90)
def xna_run_summarize(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    df = sqobject(view=view).summarize(**kwargs)
    return df


@ st.cache(ttl=90)
def xna_run_unique(sqobject, **kwargs):
    kwargs.pop('view', 'latest')
    df = sqobject().unique(**kwargs)
    if not df.empty:
        df.sort_values(by=['count'], inplace=True)
    return df


@ st.cache(ttl=90)
def xna_run_assert(sqobject, **kwargs):
    kwargs.pop('view', 'latest')
    df = sqobject().aver(status="fail", **kwargs)
    if not df.empty:
        df.rename(columns={'assert': 'status'},
                  inplace=True, errors='ignore')
    return df


def xna_build_sqobj_table() -> dict:
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


def xna_sidebar(state: SessionState, table_vals: list, page_flip: bool):
    '''Draw appropriate sidebar for the page'''

    if page_flip:
        nsval = state.xna_namespace
        hostval = state.xna_hostname
        if state.xna_table:
            tblidx = table_vals.index(state.xna_table)
        else:
            tblidx = 0
        assert_val = state.xna_assert_clicked
        view_idx = 1 if state.xna_view == 'all' else 0
    else:
        nsval = hostval = ''
        tblidx = 0
        assert_val = False
        view_idx = 0

    state.xna_namespace = st.sidebar.text_input('Namespace',
                                                value=nsval,
                                                key='xna_namespace')
    state.xna_hostname = st.sidebar.text_input('Hostname',
                                               value=hostval,
                                               key='hostname')

    table = st.sidebar.selectbox(
        'Select Table to View', tuple(table_vals), index=tblidx)

    if table != state.xna_table:
        # We need to reset the specific variables
        state.xna_query = ''
        state.assert_clicked = False
        state.uniq_clicked = 0
        state.xna_table = table

    view_vals = ('latest', 'all')
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
            'Run Assert', value=assert_val)
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

    if page_flip:
        val = state.xna_query
    else:
        val = ''
    state.xna_query = st.sidebar.text_input(
        'Filter table show results with pandas query', value=val,
        key=state.xna_table)
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


def xna_run(state: SessionState, page_flip=False):
    '''The main workhorse routine for the XNA page'''

    sqobjs = xna_build_sqobj_table()
    # All the user input is preserved in the state vars
    xna_sidebar(state, sorted(list(sqobjs.keys())), page_flip)

    df = xna_get_df(sqobjs[state.xna_table], _table=state.xna_table,
                    namespace=state.xna_namespace.split(),
                    hostname=state.xna_hostname.split(),
                    view=state.xna_view, columns=state.xna_columns)

    summ_df = xna_run_summarize(sqobjs[state.xna_table],
                                namespace=state.xna_namespace.split(),
                                hostname=state.xna_hostname.split())

    if not df.empty:
        if state.xna_query:
            try:
                show_df = df.query(state.xna_query)
            except Exception:
                st.warning('Query string throws an exception, ignoring')
                show_df = df
        else:
            show_df = df
    else:
        show_df = df

    if not show_df.empty:
        dfcols = show_df.columns.tolist()
        if state.xna_table == 'routes':
            dfcols.append('prefixlen')

        dfcols = sorted((filter(lambda x: x not in ['index', 'sqvers'],
                                dfcols)))

        grid1 = st.beta_container()
        headercol, uniq_col = st.beta_columns(2)
        with grid1:
            with headercol:
                st.write(
                    f'<h2 style="color: darkblue; font-weight: bold;">{state.xna_table} View</h2>',
                    unsafe_allow_html=True)
                if show_df.shape[0] > 256:
                    st.write(
                        f'Showing first 256 of {show_df.shape[0]} rows, use query to filter')
            with uniq_col:
                if not state.xna_uniq_clicked:
                    selindex = dfcols.index('hostname')+1
                else:
                    selindex = dfcols.index(state.xna_uniq_clicked)+1
                state.xna_uniq_clicked = st.selectbox(
                    'Distribution Count of', options=['-'] + dfcols,
                    index=selindex)

        scol1, scol2 = st.beta_columns(2)

        if state.xna_uniq_clicked != '-':
            uniq_df = xna_run_unique(sqobjs[state.xna_table],
                                     namespace=state.xna_namespace.split(),
                                     hostname=state.xna_hostname.split(),
                                     columns=[state.xna_uniq_clicked])
        else:
            uniq_df = pd.DataFrame()

        if state.xna_assert_clicked:
            assert_df = xna_run_assert(sqobjs[state.xna_table],
                                       namespace=state.xna_namespace.split())
        else:
            assert_df = pd.DataFrame()

        if not summ_df.empty:
            with scol1:
                st.subheader('Summary Information')
                st.dataframe(data=summ_df)

        if not uniq_df.empty:
            with scol2:
                if uniq_df.shape[0] > 64:
                    st.warning(
                        f'{state.xna_uniq_clicked} has cardinality > 64. Displaying top 64')
                    chart = alt.Chart(
                        uniq_df.head(64),
                        title=f'{state.xna_uniq_clicked} Distribution') \
                        .mark_bar(color='purple', tooltip=True) \
                        .encode(y=alt.Y(f'{state.xna_uniq_clicked}:N',
                                        sort='-x'),
                                x='count')
                else:

                    chart = alt.Chart(
                        uniq_df, title=f'{state.xna_uniq_clicked} Distribution') \
                        .mark_bar(color='purple', tooltip=True) \
                        .encode(y=alt.Y(f'{state.xna_uniq_clicked}:N',
                                        sort='-x'),
                                x='count')
                st.altair_chart(chart)

        if state.xna_table in ['interfaces', 'ospf', 'bgp', 'evpnVni']:
            if assert_df.empty:
                expand_assert = False
            else:
                expand_assert = True
            validate_expander = st.beta_expander('Assert',
                                                 expanded=expand_assert)
            with validate_expander:
                if not assert_df.empty:
                    st.dataframe(data=assert_df)
                elif state.xna_assert_clicked:
                    st.write('Assert passed')
                else:
                    st.write('Assert not run')

    expander = st.beta_expander('Table', expanded=True)
    with expander:
        if not show_df.empty:
            convert_dict = {
                x: 'str' for x in df.select_dtypes('category').columns}
            st.dataframe(data=sq_gui_style(show_df.head(256)
                                           .astype(convert_dict),
                                           state.xna_table),
                         height=600, width=2500)
        else:
            st.warning('No Data from query')
