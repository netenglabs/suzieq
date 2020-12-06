from types import ModuleType
from typing import List, Dict
from dataclasses import dataclass, field

import streamlit as st
import suzieq.gui.SessionState as SessionState
import altair as alt
import pandas as pd

from suzieq.sqobjects import *
from suzieq.sqobjects.tables import TablesObj
from suzieq.gui.guiutils import sq_gui_style


@dataclass
class XploreSessionState:
    namespace: str = ''
    hostname: str = ''
    table: str = ''
    view: str = ''
    query: str = ''
    columns:  List[str] = field(default_factory=list)
    uniq_clicked: int = 0
    assert_clicked: bool = False


def get_title():
    return 'Xplore'


@st.cache(ttl=90, allow_output_mutation=True)
def xna_get_df(sqobject, **kwargs):
    table = kwargs.pop('_table', '')
    view = kwargs.pop('view', 'latest')
    columns = kwargs.pop('columns', ['default'])
    if columns == ['all']:
        columns = ['*']
    if table != "tables":
        df = sqobject(view=view).get(columns=columns, **kwargs)
    else:
        df = sqobject(view=view).get(**kwargs)
    if not df.empty:
        if table == 'address':
            if 'ipAddressList' in df.columns:
                df = df.explode('ipAddressList').fillna('')
            if 'ip6AddressList' in df.columns:
                df = df.explode('ip6AddressList').fillna('')
    if not (columns == ['*'] or columns == ['default']):
        return df[columns].reset_index(drop=True)
    return df.reset_index(drop=True)


@st.cache(ttl=90)
def xna_run_summarize(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    df = sqobject(view=view).summarize(**kwargs)
    return df


@st.cache(ttl=90)
def xna_run_unique(sqobject, **kwargs):
    kwargs.pop('view', 'latest')
    df = sqobject().unique(**kwargs)
    if not df.empty:
        df.sort_values(by=['count'], ascending=False, inplace=True)
    return df


@st.cache(ttl=90)
def xna_run_assert(sqobject, **kwargs):
    kwargs.pop('view', 'latest')
    df = sqobject().aver(status="fail", **kwargs)
    if not df.empty:
        df.rename(columns={'assert': 'status'},
                  inplace=True, errors='ignore')
    return df


def xna_sidebar(state: SessionState, table_vals: list, page_flip: bool):
    '''Draw appropriate sidebar for the page'''

    if page_flip:
        nsval = state.namespace
        hostval = state.hostname
        if state.table:
            tblidx = table_vals.index(state.table)
        else:
            tblidx = 0
        assert_val = state.assert_clicked
        view_idx = 1 if state.view == 'all' else 0
    else:
        nsval = hostval = ''
        tblidx = 0
        assert_val = False
        view_idx = 0

    state.namespace = st.sidebar.text_input('Namespace',
                                            value=nsval,
                                            key='xna_namespace')
    state.hostname = st.sidebar.text_input('Hostname',
                                           value=hostval,
                                           key='hostname')

    table = st.sidebar.selectbox(
        'Select Table to View', tuple(table_vals), index=tblidx)

    if table != state.table:
        # We need to reset the specific variables
        state.query = ''
        state.assert_clicked = False
        state.uniq_clicked = 0
        state.table = table

    view_vals = ('latest', 'all')
    state.view = st.sidebar.radio("View of Data", view_vals,
                                  index=view_idx)
    fields = TablesObj().describe(table=state.table)
    if state.table != 'tables':
        colist = sorted((filter(lambda x: x not in ['index', 'sqvers'],
                                fields.name.tolist())))
        columns = st.sidebar.multiselect('Pick columns',
                                         ['default', 'all'] + colist,
                                         default=state.columns)
        if ('default' in columns or 'all' in columns) and len(columns) == 1:
            col_sel_val = True
        else:
            col_sel_val = False

        col_ok = st.sidebar.checkbox('Column Selection Done',
                                     value=col_sel_val)
        if not col_ok:
            columns = ['default']
    else:
        col_ok = True
        columns = ['default']

    if not columns:
        columns = ['default']

    state.columns = columns
    if state.table in ['interfaces', 'ospf', 'bgp', 'evpnVni']:
        state.assert_clicked = st.sidebar.checkbox(
            'Run Assert', value=assert_val)
    else:
        state.assert_clicked = False

    if not col_ok:
        st.stop()
    if ('default' in columns or 'all' in columns) and len(columns) != 1:
        st.error('Cannot select default/all with any other columns')
        st.stop()
    elif not columns:
        st.error('Columns cannot be empty')
        st.stop()

    if page_flip:
        val = state.query
    else:
        val = ''
    state.query = st.sidebar.text_input(
        'Filter table show results with pandas query', value=val,
        key=state.table)
    st.sidebar.markdown(
        "[query syntax help](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.query.html)")

    if columns == ['all']:
        columns = ['*']
    if state.table != "tables":
        col_expander = st.sidebar.beta_expander('Column Names', expanded=False)
        with col_expander:
            st.subheader(f'{state.table} column names')
            st.table(TablesObj().describe(table=state.table)
                     .query('name != "sqvers"')
                     .reset_index(drop=True).style)


def init_state(state_container: SessionState) -> XploreSessionState:
    '''Initialize session state'''

    state_container.xploreSessionState = state = XploreSessionState()

    state.columns = ['default']
    state.sqobjs = {}

    return state


def page_work(state_container: SessionState, page_flip=False):
    '''The main workhorse routine for the XNA page'''

    if hasattr(state_container, 'xploreSessionState'):
        state = getattr(state_container, 'xploreSessionState')
    else:
        state = init_state(state_container)

    sqobjs = state_container.sqobjs
    # All the user input is preserved in the state vars
    xna_sidebar(state, sorted(list(sqobjs.keys())), page_flip)

    if state.table != "tables":
        df = xna_get_df(sqobjs[state.table], _table=state.table,
                        namespace=state.namespace.split(),
                        hostname=state.hostname.split(),
                        view=state.view, columns=state.columns)
    else:
        df = xna_get_df(sqobjs[state.table], _table=state.table,
                        namespace=state.namespace.split(),
                        hostname=state.hostname.split(),
                        view=state.view)

    if state.table != "tables":
        summ_df = xna_run_summarize(sqobjs[state.table],
                                    namespace=state.namespace.split(),
                                    hostname=state.hostname.split())
    else:
        summ_df = pd.DataFrame()

    if not df.empty:
        if state.query:
            try:
                show_df = df.query(state.query)
            except Exception:
                st.warning('Query string throws an exception, ignoring')
                show_df = df
        else:
            show_df = df
    else:
        show_df = df

    if not show_df.empty:
        dfcols = show_df.columns.tolist()
        if state.table == 'routes':
            dfcols.append('prefixlen')

        dfcols = sorted((filter(lambda x: x not in ['index', 'sqvers'],
                                dfcols)))

        grid1 = st.beta_container()
        headercol, uniq_col = st.beta_columns(2)
        with grid1:
            with headercol:
                st.write(
                    f'<h2 style="color: darkblue; font-weight: bold;">{state.table} View</h2>',
                    unsafe_allow_html=True)
                if show_df.shape[0] > 256:
                    st.write(
                        f'Showing first 256 of {show_df.shape[0]} rows, use query to filter')
            with uniq_col:
                if state.table != "tables":
                    if not state.uniq_clicked:
                        selindex = dfcols.index('hostname')+1
                    else:
                        selindex = dfcols.index(state.uniq_clicked)+1

                    state.uniq_clicked = st.selectbox(
                        'Distribution Count of', options=['-'] + dfcols,
                        index=selindex)

        scol1, scol2 = st.beta_columns(2)

        if state.table != "tables" and state.uniq_clicked != '-':
            uniq_df = xna_run_unique(sqobjs[state.table],
                                     namespace=state.namespace.split(),
                                     hostname=state.hostname.split(),
                                     columns=[state.uniq_clicked])
        else:
            uniq_df = pd.DataFrame()

        if state.assert_clicked:
            assert_df = xna_run_assert(sqobjs[state.table],
                                       namespace=state.namespace.split())
        else:
            assert_df = pd.DataFrame()

        if not summ_df.empty:
            with scol1:
                st.subheader('Summary Information')
                st.dataframe(data=summ_df)

        if not uniq_df.empty:
            with scol2:
                if uniq_df.shape[0] > 32:
                    st.warning(
                        f'{state.uniq_clicked} has cardinality > 32. Displaying top 32')
                    chart = alt.Chart(
                        uniq_df.head(32),
                        title=f'{state.uniq_clicked} Distribution') \
                        .mark_bar(color='purple', tooltip=True) \
                        .encode(y=alt.Y(f'{state.uniq_clicked}:N',
                                        sort='-x'),
                                x='count')
                else:

                    chart = alt.Chart(
                        uniq_df, title=f'{state.uniq_clicked} Distribution') \
                        .mark_bar(color='purple', tooltip=True) \
                        .encode(y=alt.Y(f'{state.uniq_clicked}:N',
                                        sort='-x'),
                                x='count')
                st.altair_chart(chart)

        if state.table in ['interfaces', 'ospf', 'bgp', 'evpnVni']:
            if assert_df.empty:
                expand_assert = False
            else:
                expand_assert = True
            validate_expander = st.beta_expander('Assert',
                                                 expanded=expand_assert)
            with validate_expander:
                if not assert_df.empty:
                    st.dataframe(data=assert_df)
                elif state.assert_clicked:
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
                                           state.table),
                         height=600, width=2500)
        else:
            st.warning('No Data from query')
