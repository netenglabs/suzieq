from suzieq.gui.guiutils import sq_gui_style, gui_get_df, SuzieqMainPages, display_title
from suzieq.sqobjects import get_sqobject, get_tables
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class XploreSessionState:
    page: str = SuzieqMainPages.XPLORE
    namespace: str = ''
    hostname: str = ''
    start_time: str = ''
    end_time: str = ''
    table: str = ''
    view: str = 'latest'
    query: str = ''
    columns:  List[str] = field(default_factory=list)
    uniq_clicked: str = '-'
    assert_clicked: bool = False
    state_changed: bool = False


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
                .rename(columns={column: 'numRows',
                                 'index': column})
                .sort_values(by=['numRows'], ascending=False))


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

    table_vals = [''] + sorted(list(sqobjs.keys()))

    if state.table:
        if isinstance(state.table, list):
            tblidx = table_vals.index(state.table[0])
        else:
            tblidx = table_vals.index(state.table)
    else:
        tblidx = 0  # Default starting table
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
    with st.sidebar:
        with st.form('Xplore'):
            namespace = st.selectbox('Namespace',
                                     namespaces, key='xplore_namespace', index=nsidx)
            state.start_time = st.text_input('Start time',
                                             value=stime,
                                             key='xplore_stime')
            state.end_time = st.text_input('End time',
                                           value=etime,
                                           key='xplore_etime')

            table = st.selectbox(
                'Select Table to View', tuple(table_vals), key='xplore_table', index=tblidx)
            if table != state.table:
                # We need to reset the specific variables
                state.query = ''
                state.assert_clicked = False
                state.uniq_clicked = '-'
                state.columns = ['default']
                state.table = table

            view_vals = ('latest', 'all')
            if state.start_time and state.end_time:
                # We show everything thats happened when both times are specified
                view_idx = 1
            state.view = st.radio("View of Data", view_vals,
                                  index=view_idx, key='xplore_view')
            st.form_submit_button('Get', on_click=xplore_sync_state)

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
                                          hostnames, index=hostidx,
                                          key='xplore_hostname',
                                          on_change=xplore_sync_state)

    if state.table:
        tables_obj = get_sqobject('tables')()
        fields = tables_obj.describe(table=state.table)
        colist = sorted((filter(lambda x: x not in ['index', 'sqvers'],
                                fields.name.tolist())))
        columns = st.sidebar.multiselect('Pick columns',
                                         ['default', 'all'] + colist,
                                         key='xplore_columns',
                                         default=state.columns)
        if ('default' in columns or 'all' in columns) and len(columns) == 1:
            col_sel_val = True
        else:
            col_sel_val = False

        col_ok = st.sidebar.checkbox('Column Selection Done',
                                     key='xplore_col_done',
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
            'Run Assert', value=assert_val,  key='xplore_assert', on_change=xplore_sync_state)
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
        key='xplore_query', on_change=xplore_sync_state)

    st.sidebar.markdown(
        "[query syntax help](https://suzieq.readthedocs.io/en/latest/pandas-query-examples/)")

    if columns == ['all']:
        columns = ['*']

    if state.table:
        col_expander = st.sidebar.expander('Column Names', expanded=False)
        with col_expander:
            st.subheader(f'{state.table} column names')
            st.table(tables_obj.describe(table=state.table)
                     .query('name != "sqvers"')
                     .reset_index(drop=True).astype(str).style)


def page_work(state_container):
    '''The main workhorse routine for the Xplore page'''

    if 'xploreSessionState' not in state_container:
        state_container['xploreSessionState'] = None

    state = state_container.xploreSessionState

    if 'xplore_df' not in state_container:
        state_container['xplore_df'] = None

    url_params = st.experimental_get_query_params()
    page = url_params.pop('page', '')
    if not state and get_title() in page:
        if url_params and not all(not x for x in url_params.values()):
            for key in url_params:
                if key == 'columns':
                    # This needs to be a list
                    continue
                val = url_params.get(key, '')
                if isinstance(val, list):
                    val = val[0]
                    url_params[key] = val
                if key in ['assert_clicked', 'run_on_start']:
                    if val == 'True':
                        url_params[key] = True
                    else:
                        url_params[key] = False
            state = XploreSessionState(**url_params)
            state_container.xploreSessionState = state
        else:
            state = XploreSessionState()
            state_container.xploreSessionState = state
    elif not state:
        state = XploreSessionState()
        state_container.xploreSessionState = state

    sqobjs = state_container.sqobjs

    # All the user input is preserved in the state vars
    xplore_sidebar(state, sqobjs)
    xplore_run()


def xplore_sync_state():
    '''Update session state with latest widget state'''
    wsstate = st.session_state
    state = wsstate.xploreSessionState

    state_changed = False
    if wsstate.xplore_namespace != state.namespace:
        state.namespace = wsstate.xplore_namespace
        state_changed = True

    if wsstate.xplore_hostname != state.hostname:
        state.hostname = wsstate.xplore_hostname
        state_changed = True
    if wsstate.xplore_stime != state.start_time:
        state.start_time = wsstate.xplore_stime
        state_changed = True
    if wsstate.xplore_etime != state.end_time:
        state.end_time = wsstate.xplore_etime
        state_changed = True
    if wsstate.xplore_view != state.view:
        state.view = wsstate.xplore_view
        state_changed = True
    xplore_col_done = wsstate.get('xplore_col_done', False)
    if xplore_col_done and (wsstate.xplore_columns != state.columns):
        state.columns = wsstate.xplore_columns
        state_changed = True
    if wsstate.xplore_query != state.query:
        state.query = wsstate.xplore_query
        state_changed = True
    assert_clicked = wsstate.get('xplore_assert', '')
    if assert_clicked and (assert_clicked != state.assert_clicked):
        state.assert_clicked = wsstate.xplore_assert
        state_changed = True
    uniq_sel = wsstate.get('xplore_uniq_col', '')
    if uniq_sel and (state.uniq_clicked != uniq_sel):
        state.uniq_clicked = uniq_sel
        state_changed = True

    if wsstate.xplore_table != state.table:
        # Reset all dependent vars when table changes
        state.table = wsstate.xplore_table
        state.query = ''
        state.assert_clicked = False
        state.uniq_clicked = '-'
        state.columns = ['default']
        state_changed = True

    state.state_changed = state_changed


def xplore_create_layout(state):
    '''Create all the layout widgets for Xplore page

    This helps avoid bad screen effects such as screen shifting, 
    jerkiness etc. when changing or updating the page
    '''
    grid1 = st.container()
    with grid1:
        headercol, uniq_col = st.columns(2)
        header_ph = headercol.empty()
        uniq_ph = uniq_col.empty()

        scol1, scol2 = st.columns(2)
        scol1_ph = scol1.empty()
        scol2_ph = scol2.empty()
        if state.table in ['interfaces', 'ospf', 'bgp', 'evpnVni']:
            validate_expander = st.expander(
                'Assert', expanded=state.assert_clicked)
        else:
            validate_expander = None
        table_expander = st.expander('Table', expanded=True)

    return {
        'header_ph': header_ph,  # summary header
        'uniq_col_ph': uniq_ph,  # unique column selector
        'summ_ph': scol1_ph,  # summary table
        'uniq_ph': scol2_ph,  # unique table
        'assert_expander': validate_expander,  # assert expander
        'table_expander': table_expander,  # table dataframe expander
    }


def xplore_run():
    wsstate = st.session_state
    state = wsstate.xploreSessionState

    if not state.table:
        return

    layout = xplore_create_layout(state)
    sqobj = get_sqobject(state.table)
    df = gui_get_df(sqobj, _table=state.table,
                    namespace=state.namespace.split(),
                    hostname=state.hostname.split(),
                    start_time=state.start_time, end_time=state.end_time,
                    view=state.view, columns=state.columns)

    wsstate['xplore_df'] = df
    if not df.empty:
        if 'error' in df.columns:
            st.error(df.iloc[0].error)
            st.experimental_set_query_params(**asdict(state))
            st.stop()
            return

    if state.query:
        try:
            show_df = df.query(state.query).reset_index(drop=True)
            query_str = state.query
        except Exception:
            st.warning('Query string throws an exception, ignoring')
            show_df = df
            query_str = ''
    else:
        show_df = df
        query_str = ''

    if not show_df.empty:
        xplore_draw_summary_df(layout, state.table, state, sqobj, query_str)
        xplore_draw_uniq_histogram(layout, state.table, state,
                                   wsstate, show_df)
        xplore_draw_assert_df(layout, state, sqobj)

    xplore_draw_table_df(layout, state.table, show_df)

    st.experimental_set_query_params(**asdict(state))
    state.state_changed = False


def xplore_draw_summary_df(layout, table, state, sqobj, query_str):
    '''Display the summary dataframe'''
    summ_df = xplore_run_summarize(sqobj,
                                   namespace=state.namespace.split(),
                                   hostname=state.hostname.split(),
                                   start_time=state.start_time,
                                   end_time=state.end_time,
                                   query_str=query_str)

    header_col = layout['header_ph']
    header_col.write(
        f'<h2 style="color: darkblue; font-weight: bold;">{state.table} View</h2>',
        unsafe_allow_html=True)

    summ_ph = layout['summ_ph']
    if not summ_df.empty:
        summ_ph.subheader('Summary Information')
        summ_ph.dataframe(data=summ_df.astype(str))


def xplore_draw_uniq_histogram(layout, table, state, wsstate, show_df):
    '''Display the unique histogram'''

    dfcols = show_df.columns.tolist()
    if (state.table == 'routes' and 'prefix' in dfcols and
            'prefixlen' not in dfcols):
        dfcols.append('prefixlen')

    uniq_col = layout['uniq_col_ph']
    dfcols = sorted((filter(lambda x: x not in ['index', 'sqvers'],
                            dfcols)))
    with uniq_col:
        if (state.uniq_clicked == '-' or
                state.uniq_clicked not in dfcols):
            if 'hostname' in dfcols:
                selindex = dfcols.index('hostname')+1
                uniq_sel = 'hostname'
            else:
                uniq_sel = '-'
                selindex = 0
        elif state.uniq_clicked in dfcols:
            uniq_sel = state.uniq_clicked
            selindex = dfcols.index(state.uniq_clicked)+1
        else:
            uniq_sel = '-'
            selindex = 0

        if 'xplore_uniq_col' not in wsstate:
            state.uniq_clicked = st.selectbox(
                'Distribution Count of', options=['-'] + dfcols,
                index=selindex, key='xplore_uniq_col', on_change=xplore_sync_state)
        else:
            wsstate.xplore_uniq_col = uniq_sel
            state.uniq_clicked = st.selectbox(
                'Distribution Count of', options=['-'] + dfcols,
                index=selindex,
                key='xplore_uniq_col', on_change=xplore_sync_state)

    scol2 = layout['uniq_ph']

    if state.uniq_clicked != '-':
        uniq_df = xplore_run_unique(show_df,
                                    columns=state.uniq_clicked)
    else:
        uniq_df = pd.DataFrame()

    if not uniq_df.empty:
        if uniq_df.shape[0] > 16:
            scol2.warning(
                f'{state.uniq_clicked} has cardinality of {uniq_df.shape[0]}. Displaying top 16')
            chart = alt.Chart(
                uniq_df.head(16),
                title=f'{state.uniq_clicked} Distribution') \
                .mark_bar(color='purple', tooltip=True) \
                .encode(y=alt.Y(f'{state.uniq_clicked}:N',
                                sort='-x'),
                        x='numRows')
        else:
            chart = alt.Chart(
                uniq_df, title=f'{state.uniq_clicked} Distribution') \
                .mark_bar(color='purple', tooltip=True) \
                .encode(y=alt.Y(f'{state.uniq_clicked}:N',
                                sort='-x'),
                        x='numRows')
        scol2.altair_chart(chart)


def xplore_draw_assert_df(layout, state, sqobj):
    '''Display the assert dataframe'''
    if state.assert_clicked:
        assert_df = xplore_run_assert(sqobj,
                                      start_time=state.start_time,
                                      end_time=state.end_time,
                                      namespace=state.namespace.split())
    else:
        assert_df = pd.DataFrame()

    if state.table in ['interfaces', 'ospf', 'bgp', 'evpnVni']:
        if assert_df.empty:
            expand_assert = False
        else:
            expand_assert = True
        assert_expander = layout['assert_expander']
        with assert_expander:
            if not assert_df.empty:
                st.dataframe(data=assert_df)
            elif state.assert_clicked:
                st.write('Assert passed')
            else:
                st.write('Assert not run')


def xplore_draw_table_df(layout, table, show_df):
    '''Display the table dataframe'''
    expander = layout['table_expander']
    with expander:
        if show_df.shape[0] > 256:
            st.write(
                f'Showing first 256 of {show_df.shape[0]} rows, use query to filter')
        if not show_df.empty:
            convert_dict = {
                x: 'str' for x in show_df.select_dtypes('category').columns}
            st.dataframe(data=sq_gui_style(show_df.head(256)
                                           .astype(convert_dict),
                                           table),
                         height=600, width=2500)
        else:
            st.warning('No Data from query')
