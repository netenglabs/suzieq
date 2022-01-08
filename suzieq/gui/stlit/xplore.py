from dataclasses import dataclass, field, asdict
from typing import List

import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, JsCode

from suzieq.gui.stlit.guiutils import (gui_get_df, sq_gui_style,
                                       SuzieqMainPages)
from suzieq.gui.stlit.pagecls import SqGuiPage
from suzieq.sqobjects import get_sqobject, get_tables


@dataclass
class XploreSessionState:
    '''Session state for Xplore page'''
    page: str = SuzieqMainPages.XPLORE.value
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


class XplorePage(SqGuiPage):
    '''Page for exploratory analysis'''
    _title: str = SuzieqMainPages.XPLORE.value
    _state: XploreSessionState = XploreSessionState()

    @property
    def add_to_menu(self) -> bool:
        return True

    def build(self):
        self._get_state_from_url()
        self._create_sidebar()
        layout = self._create_layout()
        self._render(layout)
        self._save_page_url()

    # pylint: disable=too-many-statements
    def _create_sidebar(self) -> None:

        state = self._state
        stime = state.start_time
        etime = state.end_time

        tables = filter(
            lambda x: x not in ['path', 'tables', 'ospfIf', 'ospfNbr',
                                'topmem', 'topcpu', 'ifCounters', 'time'],
            get_tables()
        )
        table_vals = [''] + sorted(tables)

        if state.table:
            if isinstance(state.table, list):
                tblidx = table_vals.index(state.table[0])
            else:
                tblidx = table_vals.index(state.table)
        else:
            tblidx = 0  # Default starting table
        assert_val = state.assert_clicked
        view_idx = 1 if state.view == 'all' else 0

        devdf = gui_get_df('device', columns=['namespace', 'hostname'])
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
                                         namespaces, key='xplore_namespace',
                                         index=nsidx)
                state.start_time = st.text_input('Start time',
                                                 value=stime,
                                                 key='xplore_stime')
                state.end_time = st.text_input('End time',
                                               value=etime,
                                               key='xplore_etime')

                table = st.selectbox(
                    'Select Table to View', tuple(table_vals),
                    key='xplore_table', index=tblidx)
                if table != state.table:
                    # We need to reset the specific variables
                    state.query = ''
                    state.assert_clicked = False
                    state.uniq_clicked = '-'
                    state.columns = ['default']
                    state.table = table

                view_vals = ('latest', 'all')
                if state.start_time and state.end_time:
                    # Show everything thats happened if both times are given
                    view_idx = 1
                state.view = st.radio("View of Data", view_vals,
                                      index=view_idx, key='xplore_view')
                st.form_submit_button('Get', on_click=self._sync_state)

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
                                              on_change=self._sync_state)

        if state.table:
            tables_obj = get_sqobject('tables')(start_time=state.start_time,
                                                end_time=state.end_time,
                                                view=state.view)
            fields = tables_obj.describe(table=state.table)
            colist = sorted((filter(lambda x: x not in ['index', 'sqvers'],
                                    fields.name.tolist())))
            columns = st.sidebar.multiselect('Pick columns',
                                             ['default', 'all'] + colist,
                                             key='xplore_columns',
                                             default=state.columns)
            col_sel_val = (('default' in columns or 'all' in columns)
                           and len(columns) == 1)

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
                'Run Assert', value=assert_val,  key='xplore_assert',
                on_change=self._sync_state)
        else:
            state.assert_clicked = False

        state.query = st.sidebar.text_input(
            'Filter results with pandas query', value=state.query,
            key='xplore_query', on_change=self._sync_state)

        st.sidebar.markdown(
            "[query syntax help]"
            "(https://suzieq.readthedocs.io/en/latest/pandas-query-examples/)")

        if columns == ['all']:
            columns = ['*']

        if state.table:
            col_expander = st.sidebar.expander('Column Names', expanded=False)
            with col_expander:
                st.subheader(f'{state.table} column names')
                st.table(tables_obj.describe(table=state.table)
                         .query('name != "sqvers"')
                         .reset_index(drop=True).astype(str).style)

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

    def _create_layout(self) -> None:
        grid1 = st.container()
        with grid1:
            headercol, uniq_col = st.columns(2)
            header_ph = headercol.empty()
            uniq_ph = uniq_col.empty()

            scol1, scol2 = st.columns(2)
            scol1_ph = scol1.empty()
            scol2_ph = scol2.empty()
            if self._state.table in ['interfaces', 'ospf', 'bgp', 'evpnVni']:
                validate_ph = st.empty()
            else:
                validate_ph = None
            table_ph = st.empty()

        return {
            'header': header_ph,  # summary header
            'uniq_col': uniq_ph,  # unique column selector
            'summary': scol1_ph,  # summary table
            'uniq': scol2_ph,  # unique table
            'assert': validate_ph,  # assert expander
            'table': table_ph,  # table dataframe expander
        }

    def _render(self, layout: dict) -> None:

        state = self._state

        if not state.table:
            return

        sqobj = get_sqobject(state.table)
        df = gui_get_df(state.table,
                        namespace=state.namespace.split(),
                        hostname=state.hostname.split(),
                        start_time=state.start_time, end_time=state.end_time,
                        view=state.view, columns=state.columns)

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
            except Exception as ex:  # pylint: disable=broad-except
                st.error(f'Invalid query string: {ex}')
                st.stop()
                query_str = ''
        else:
            show_df = df
            query_str = ''

        if not show_df.empty:
            self._draw_summary_df(layout, sqobj, query_str)
            self._draw_assert_df(layout, sqobj)

        self._draw_table_df(layout, show_df)

    def _sync_state(self) -> None:
        wsstate = st.session_state
        state = self._state

        if wsstate.xplore_namespace != state.namespace:
            state.namespace = wsstate.xplore_namespace

        if wsstate.xplore_hostname != state.hostname:
            state.hostname = wsstate.xplore_hostname
        if wsstate.xplore_stime != state.start_time:
            state.start_time = wsstate.xplore_stime
        if wsstate.xplore_etime != state.end_time:
            state.end_time = wsstate.xplore_etime
        if wsstate.xplore_view != state.view:
            state.view = wsstate.xplore_view
        xplore_col_done = wsstate.get('xplore_col_done', False)
        if xplore_col_done and (wsstate.xplore_columns != state.columns):
            state.columns = wsstate.xplore_columns
        if wsstate.xplore_query != state.query:
            state.query = wsstate.xplore_query
        assert_clicked = wsstate.get('xplore_assert', '')
        if assert_clicked and (assert_clicked != state.assert_clicked):
            state.assert_clicked = wsstate.xplore_assert
        uniq_sel = wsstate.get('xplore_uniq_col', '')
        if uniq_sel and (state.uniq_clicked != uniq_sel):
            state.uniq_clicked = uniq_sel

        if wsstate.xplore_table != state.table:
            # Reset all dependent vars when table changes
            state.table = wsstate.xplore_table
            state.query = ''
            state.assert_clicked = False
            state.uniq_clicked = '-'
            state.columns = ['default']

    def _draw_table_df(self, layout, show_df):
        '''Display the table dataframe'''
        expander = layout['table'].expander('Table', expanded=True)

        with expander:
            if not show_df.empty:
                self._draw_aggrid_df(layout, show_df)
            else:
                st.warning('No Data from query')

    def _draw_aggrid_df(self, layout, df):

        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(paginationPageSize=25)

        gb.configure_default_column(floatingFilter=True)
        if any(x in df.columns for x in ['state', 'status']):
            jscode = self._aggrid_style()
            gb.configure_column("state", floatingFilter=True,
                                cellStyle=jscode)

        gb.configure_grid_options(
            domLayout='normal', preventDefaultOnContextMenu=True)
        gridOptions = gb.build()

        grid_response = AgGrid(
            df,
            gridOptions=gridOptions,
            allow_unsafe_jscode=True,
            data_return_mode='FILTERED',
            update_mode=GridUpdateMode.FILTERING_CHANGED,
            theme='streamlit',
        )

        selected = grid_response['selected_rows']
        selected_df = pd.DataFrame(selected)
        if not selected_df.empty:
            self._draw_uniq_histogram(layout, selected_df)
        else:
            new_data = grid_response['data']
            new_df = pd.DataFrame(new_data)
            self._draw_uniq_histogram(layout, new_df)

    def _aggrid_style(self):
        '''Style the cells based on value'''
        table = self._state.table

        if table == 'bgp':
            a = """
            function(params) {
                if (params.value === 'NotEstd') {
                    return {
                        'color': 'white',
                        'backgroundColor': 'darkred'
                    }
                }
            };
            """
        elif table == 'device':
            a = """
            function(params) {
                if (params.value === 'dead') {
                    return {
                        'color': 'white',
                        'backgroundColor': 'darkred'
                    }
                } else if (params.value === 'neverpoll') {
                    return {
                        'color': 'white',
                        'backgroundColor': 'red'
                    }
                }
            };
            """
        elif table == 'arpnd':
            a = """
            function(params) {
                if (params.value === 'failed') {
                    return {
                        'color': 'white',
                        'backgroundColor': 'darkred'
                    }
                }
            };
            """
        elif table in ['interfaces', 'evpnVni', 'address']:
            a = """
            function(params) {
                if (params.value === 'down') {
                    return {
                        'color': 'white',
                        'backgroundColor': 'red'
                    }
                } else if (params.value === 'notConnected') {
                    return {
                        'color': 'black',
                        'backgroundColor': 'gray'
                    }
                } else if (params.value === 'errDisabled') {
                    return {
                        'color': 'white',
                        'backgroundColor': 'darkred'
                    }
                }
            };
            """
        elif table == 'vlan':
            a = """
            function(params) {
                if (params.value != 'active') {
                    return {
                        'color': 'white',
                        'backgroundColor': 'darkred'
                    }
                }
            };
            """
        elif table == 'sqPoller':
            a = """
            function(params) {
                if (params.value != 0 or params.value != 200) {
                    return {
                        'color': 'white',
                        'backgroundColor': 'darkred'
                    }
                }
            };
            """

        return JsCode(a)

    def _draw_summary_df(self, layout, sqobj, query_str):
        '''Display the summary dataframe'''
        summ_df = self._run_summarize(
            sqobj,
            namespace=self._state.namespace.split(),
            hostname=self._state.hostname.split(),
            start_time=self._state.start_time,
            end_time=self._state.end_time,
            query_str=query_str)

        header_col = layout['header']
        header_col.write(
            f'<h2 style="color: darkblue; font-weight: bold;">'
            f'{self._state.table} View</h2>',
            unsafe_allow_html=True)

        summ_ph = layout['summary']
        if not summ_df.empty:
            with summ_ph:
                st.subheader('Summary Information')
                st.dataframe(summ_df.astype(str))

    def _draw_uniq_histogram(self, layout, show_df):
        '''Display the unique histogram'''

        state = self._state
        dfcols = show_df.columns.tolist()
        if (state.table == 'routes' and 'prefix' in dfcols and
                'prefixlen' not in dfcols):
            dfcols.append('prefixlen')

        uniq_col = layout['uniq_col']
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

            if 'xplore_uniq_col' not in st.session_state:
                state.uniq_clicked = st.selectbox(
                    'Distribution Count of', options=['-'] + dfcols,
                    index=selindex, key='xplore_uniq_col',
                    on_change=self._sync_state)
            else:
                st.session_state.xplore_uniq_col = uniq_sel
                state.uniq_clicked = st.selectbox(
                    'Distribution Count of', options=['-'] + dfcols,
                    index=selindex,
                    key='xplore_uniq_col', on_change=self._sync_state)

        scol2 = layout['uniq']

        if state.uniq_clicked != '-':
            uniq_df = self._run_unique(show_df,
                                       columns=self._state.uniq_clicked)
        else:
            uniq_df = pd.DataFrame()

        if not uniq_df.empty:
            if uniq_df.shape[0] > 16:
                scol2.warning(
                    f'{state.uniq_clicked} has cardinality of '
                    f'{uniq_df.shape[0]}, displaying top 16')
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

    def _draw_assert_df(self, layout, sqobj):
        '''Display the assert dataframe'''
        if self._state.assert_clicked:
            assert_df = self._run_assert(
                sqobj,
                start_time=self._state.start_time,
                end_time=self._state.end_time,
                namespace=self._state.namespace.split())
        else:
            assert_df = pd.DataFrame()

        if self._state.table in ['interfaces', 'ospf', 'bgp', 'evpnVni']:

            assert_expander = layout['assert'].expander(
                'Assert', expanded=self._state.assert_clicked)
            with assert_expander:
                if not assert_df.empty:
                    convert_dict = {
                        x: 'str'
                        for x in assert_df.select_dtypes('category').columns}
                    st.dataframe(data=sq_gui_style(assert_df
                                                   .astype(convert_dict),
                                                   self._state.table, True))
                elif self._state.assert_clicked:
                    st.write('Assert passed')
                else:
                    st.write('Assert not run')

    @st.cache(ttl=90)
    def _run_summarize(self, sqobject, **kwargs):
        '''Get summarize dataframe for the object in question'''
        view = kwargs.pop('view', 'latest')
        stime = kwargs.pop('start_time', '')
        etime = kwargs.pop('end_time', '')
        df = sqobject(view=view, start_time=stime,
                      end_time=etime).summarize(**kwargs)
        # Leaving this commented to avoid future heartburn in case someone
        # tries to do this. It didn't fix the Timedelta being added to display
        # if not df.empty:
        #     if 'upTimeStat' in df.T.columns:
        #         df.T['upTimeStat'] = df.T.upTimeStat \
        #               .apply(lambda x: [str(y) for y in x])

        return df

    def _run_unique(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        '''Compute the distribution counts for the dataframe provided'''
        column = kwargs.pop('columns', '')
        if not df.empty:
            if column == 'prefixlen' and 'prefixlen' not in df.columns:
                # Special handling for prefixlen
                df['prefixlen'] = df['prefix'].str.split('/').str[1]

            if df.apply(lambda x: isinstance(x[column], np.ndarray),
                        axis=1).all():
                idf = df.explode(column).dropna(how='any')
            else:
                idf = df

            r = idf[column].value_counts()
            return (pd.DataFrame({column: r})
                    .reset_index()
                    .rename(columns={column: 'numRows',
                                     'index': column})
                    .sort_values(by=['numRows'], ascending=False))
        return pd.DataFrame()

    @st.cache(ttl=90)
    def _run_assert(self, sqobject, **kwargs):
        kwargs.pop('view', 'latest')
        stime = kwargs.pop('start_time', '')
        etime = kwargs.pop('end_time', '')
        df = sqobject(start_time=stime, end_time=etime) \
            .aver(status="fail", **kwargs)
        if not df.empty:
            df.rename(columns={'assert': 'status'},
                      inplace=True, errors='ignore')
        return df
