from suzieq.gui.guiutils import sq_gui_style, gui_get_df
from suzieq.sqobjects.tables import TablesObj
from suzieq.sqobjects import *
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class XploreSessionState:
    namespace: str = ''
    hostname: str = ''
    start_time: str = ''
    end_time: str = ''
    table: str = 'device'
    view: str = 'latest'
    query: str = ''
    columns:  List[str] = field(default_factory=list)
    uniq_clicked: str = ''
    assert_clicked: bool = False


def get_title():
    return 'Xplore'


@st.cache(ttl=90)
def xplore_run_summarize(sqobject, **kwargs):
    view = kwargs.pop('view', 'latest')
    stime = kwargs.pop('start_time', '')
    etime = kwargs.pop('end_time', '')
    df = sqobject(view=view, start_time=stime,
                  end_time=etime).summarize(**kwargs)
    # Leaving this commented to avoid future heartburn in case someone
    # tries to do this. It didn't fix the Timedelta being added to display
    # if not df.empty:
    #     if 'upTimeStat' in df.T.columns:
    #         df.T['upTimeStat'] = df.T.upTimeStat.apply(lambda x: [str(y)
    #                                                               for y in x])

    return df


def xplore_run_unique(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    '''Compute the distribution counts for the dataframe provided'''
    column = kwargs.pop('columns', '')
    if not df.empty:
        if column == 'prefixlen' and 'prefixlen' not in df.columns:
            # Special handling for prefixlen
            df['prefixlen'] = df['prefix'].str.split('/').str[1]

        if df.apply(lambda x: isinstance(x[column], np.ndarray), axis=1).all():
            idf = df.explode(column).dropna(how='any')
        else:
            idf = df

        r = idf[column].value_counts()
        return (pd.DataFrame({column: r})
                .reset_index()
                .rename(columns={column: 'count',
                                 'index': column})
                .sort_values(by=['count'], ascending=False))


@st.cache(ttl=90)
def xplore_run_assert(sqobject, **kwargs):
    kwargs.pop('view', 'latest')
    stime = kwargs.pop('start_time', '')
    etime = kwargs.pop('end_time', '')
    df = sqobject(start_time=stime, end_time=etime) \
        .aver(status="fail", **kwargs)
    if not df.empty:
        df.rename(columns={'assert': 'status'},
                  inplace=True, errors='ignore')
    return df


def xplore_sidebar(state, sqobjs: dict):
    '''Draw appropriate sidebar for the page'''

    stime = state.start_time
    etime = state.end_time

    table_vals = sorted(list(sqobjs.keys()))

    if state.table:
        if isinstance(state.table, list):
            tblidx = table_vals.index(state.table[0])
        else:
            tblidx = table_vals.index(state.table)
    else:
        tblidx = table_vals.index('device')  # Default starting table
    assert_val = state.assert_clicked
    view_idx = 1 if state.view == 'all' else 0

    devdf = gui_get_df(sqobjs['device'], columns=['namespace', 'hostname'])
    if devdf.empty:
        st.error('Unable to retrieve any namespace info')
        st.stop()

    namespaces = [""]
    namespaces.extend(sorted(devdf.namespace.unique().tolist()))
    if state.namespace:
        nsidx = namespaces.index(state.namespace)
    else:
        nsidx = 0
    namespace = st.sidebar.selectbox('Namespace',
                                     namespaces, index=nsidx)

    if namespace != state.namespace:
        state.hostname = None
        state.namespace = namespace

    hostnames = [""]
    if state.namespace:
        hostlist = devdf.query(f'namespace=="{state.namespace}"') \
                        .hostname.unique().tolist()
    else:
        hostlist = devdf.hostname.unique().tolist()
    hostnames.extend(sorted(hostlist))
    if state.hostname:
        hostidx = hostnames.index(state.hostname)
    else:
        hostidx = 0
    state.hostname = st.sidebar.selectbox('Hostname',
                                          hostnames, index=hostidx)

    state.start_time = st.sidebar.text_input('Start time',
                                             value=stime,
                                             key='stime')
    state.end_time = st.sidebar.text_input('End time',
                                           value=etime,
                                           key='etime')
    table = st.sidebar.selectbox(
        'Select Table to View', tuple(table_vals), index=tblidx)

    if table != state.table:
        # We need to reset the specific variables
        state.query = ''
        state.assert_clicked = False
        state.uniq_clicked = 0
        state.table = table
        state.columns = 'default'

    view_vals = ('latest', 'all')
    if state.start_time and state.end_time:
        # We show everything thats happened when both times are specified
        view_idx = 1
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
        st.experimental_set_query_params(**asdict(state))
        st.stop()
    if ('default' in columns or 'all' in columns) and len(columns) != 1:
        st.error('Cannot select default/all with any other columns')
        st.experimental_set_query_params(**asdict(state))
        st.stop()
    elif not columns:
        st.error('Columns cannot be empty')
        st.experimental_set_query_params(**asdict(state))
        st.stop()

    state.query = st.sidebar.text_input(
        'Filter results with pandas query', value=state.query,
        key=state.table)
    st.sidebar.markdown(
        "[query syntax help](https://suzieq.readthedocs.io/en/latest/pandas-query-examples/)")

    if columns == ['all']:
        columns = ['*']
    if state.table != "tables":
        col_expander = st.sidebar.beta_expander('Column Names', expanded=False)
        with col_expander:
            st.subheader(f'{state.table} column names')
            st.table(TablesObj().describe(table=state.table)
                     .query('name != "sqvers"')
                     .reset_index(drop=True).style)


def page_work(state_container, page_flip: bool):
    '''The main workhorse routine for the Xplore page'''

    if not state_container.xploreSessionState:
        state_container.xploreSessionState = XploreSessionState()
        state = state_container.xploreSessionState
        state.columns = ['default']
    else:
        state = state_container.xploreSessionState

    url_params = st.experimental_get_query_params()
    page = url_params.pop('page', '')
    if get_title() in page:
        if url_params and not all(not x for x in url_params.values()):
            for key in url_params:
                if key == 'columns':
                    # This needs to be a list
                    continue
                val = url_params.get(key, '')
                if isinstance(val, list):
                    val = val[0]
                    url_params[key] = val
                if key == '':
                    if val == 'True':
                        url_params[key] = True
                    else:
                        url_params[key] = False
            state.__init__(**url_params)

    sqobjs = state_container.sqobjs
    # All the user input is preserved in the state vars
    xplore_sidebar(state, sqobjs)

    if state.table != "tables":
        df = gui_get_df(sqobjs[state.table], _table=state.table,
                        namespace=state.namespace.split(),
                        hostname=state.hostname.split(),
                        start_time=state.start_time, end_time=state.end_time,
                        view=state.view, columns=state.columns)
        if state.table == "device" and 'uptime' in df.columns:
            df.drop(columns=['uptime'], inplace=True)
    else:
        df = gui_get_df(sqobjs[state.table], _table=state.table,
                        namespace=state.namespace.split(),
                        hostname=state.hostname.split(),
                        start_time=state.start_time, end_time=state.end_time,
                        view=state.view)

    query_str = ''
    if not df.empty:
        if 'error' in df.columns:
            st.error(df.iloc[0].error)
            st.experimental_set_query_params(**asdict(state))
            st.stop()
        if state.query:
            try:
                show_df = df.query(state.query)
                query_str = state.query
            except Exception:
                st.warning('Query string throws an exception, ignoring')
                show_df = df
                query_str = ''
        else:
            show_df = df
    else:
        show_df = df

    if state.table != "tables":
        summ_df = xplore_run_summarize(sqobjs[state.table],
                                       namespace=state.namespace.split(),
                                       hostname=state.hostname.split(),
                                       start_time=state.start_time,
                                       end_time=state.end_time,
                                       query_str=query_str)
    else:
        summ_df = pd.DataFrame()

    if not show_df.empty:
        dfcols = show_df.columns.tolist()
        if (state.table == 'routes' and 'prefix' in dfcols and
                'prefixlen' not in dfcols):
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
                    if (not state.uniq_clicked or
                            state.uniq_clicked not in dfcols):
                        if 'hostname' in dfcols:
                            selindex = dfcols.index('hostname')+1
                        else:
                            selindex = 1
                    elif state.uniq_clicked in dfcols:
                        selindex = dfcols.index(state.uniq_clicked)+1

                    state.uniq_clicked = st.selectbox(
                        'Distribution Count of', options=['-'] + dfcols,
                        index=selindex, key='distcount')

        scol1, scol2 = st.beta_columns(2)

        if state.table != "tables" and state.uniq_clicked != '-':
            uniq_df = xplore_run_unique(show_df,
                                        columns=state.uniq_clicked)
        else:
            uniq_df = pd.DataFrame()

        if state.assert_clicked:
            assert_df = xplore_run_assert(sqobjs[state.table],
                                          start_time=state.start_time,
                                          end_time=state.end_time,
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

        st.experimental_set_query_params(**asdict(state))
