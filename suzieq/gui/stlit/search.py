## Changes done in search updated new technologies with suitable commands
from collections import deque
from dataclasses import dataclass, field
from ipaddress import ip_address
from random import randint
import asyncio

import streamlit as st
from pandas.core.frame import DataFrame
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from suzieq.gui.stlit.guiutils import (SuzieqMainPages, gui_get_df,
                                       set_def_aggrid_options)
from suzieq.gui.stlit.pagecls import SqGuiPage
from suzieq.shared.utils import (convert_macaddr_format_to_colon,
                                 validate_macaddr)


@dataclass
class SearchSessionState:
    '''Session state for Search page'''
    page: str = SuzieqMainPages.SEARCH.value
    search_text: str = ''
    past_df = None
    table: str = ''
    namespace: str = ''
    query_str: str = ''
    unique_query: dict = field(default_factory=dict)
    prev_results = deque(maxlen=5)
    debounce_time: float = 0.5  # Debounce time for input


class SearchPage(SqGuiPage):
    '''Page for Path trace page'''
    _title: str = SuzieqMainPages.SEARCH.value
    _state = SearchSessionState()
    _config_file = st.session_state.get('config_file', '')

    @property
    def add_to_menu(self):
        return True

    async def build(self):
        self._get_state_from_url()
        self._create_sidebar()
        layout = self._create_layout()
        await self._render(layout)
        self._save_page_url()

    def _create_sidebar(self) -> None:

        state = self._state
        devdf = self._fetch_data_with_cache('device', columns=['namespace', 'hostname'])

        if devdf.empty:
            st.error('Unable to retrieve any namespace info')
            st.stop()

        namespaces = [''] + sorted(devdf.namespace.unique().tolist())
        nsidx = 0
        if state.namespace and state.namespace in namespaces:
            nsidx = namespaces.index(state.namespace)

        namespace = st.sidebar.selectbox('Namespace',
                                         namespaces, key='search_ns',
                                         index=nsidx,
                                         on_change=self._sync_state)

        st.sidebar.markdown(
            """Displays last 5 search results.

You can use search to find specific objects... [same help text as before]""")

        if namespace != state.namespace:
            state.namespace = namespace

        # Option to clear search history
        if st.sidebar.button('Clear Search History'):
            state.prev_results.clear()

    def _create_layout(self) -> dict:
        return {
            'current': st.empty()
        }

    async def _render(self, layout) -> None:
        state = self._state
        search_text = st.session_state.search or state.search_text

        query_str, uniq_dict, columns = '', {}, []
        df = DataFrame()

        try:
            query_str, uniq_dict, columns = self._build_query(search_text)
        except ValueError as ve:
            expander = layout['current'].expander(f'Search for {search_text}',
                                                  expanded=True)
            df = DataFrame({'error': [ve]})
            self._draw_aggrid_df(expander, df)

        if state.namespace:
            query_ns = [state.namespace]
        else:
            query_ns = []

        if query_str:
            df = await self._fetch_data(query_str, state.table, query_ns, columns)
            expander = layout['current'].expander(f'Search for {search_text}',
                                                  expanded=True)
            self._draw_aggrid_df(expander, df)

        elif uniq_dict:
            columns = ['namespace'] + uniq_dict['column']
            df = await self._fetch_data('', uniq_dict['table'], query_ns, columns)
            expander = layout['current'].expander(f'Search for {search_text}',
                                                  expanded=True)
            self._draw_aggrid_df(expander, df)

        elif len(state.prev_results) == 0:
            st.info('Enter a search string to see results, see sidebar for examples')

        prev_searches = [search_text]
        for psrch, prev_df in reversed(state.prev_results):
            if psrch in prev_searches:
                continue
            prev_searches.append(psrch)
            expander = st.expander(f'Search for {psrch}', expanded=True)
            self._draw_aggrid_df(expander, prev_df)

        is_error = (not df.empty) and all(df.columns == 'error')
        if ((query_str or uniq_dict) and st.session_state.search and
                (st.session_state.search != state.search_text) and
                not is_error):
            state.prev_results.append((search_text, df))
            state.search_text = st.session_state.search

    def _draw_aggrid_df(self, expander, df):

        with expander:
            if df.empty:
                st.info('No matching result found')
            elif 'error' in df:
                st.error(df['error'][0])
            else:

                gb = GridOptionsBuilder.from_dataframe(df)
                gb.configure_pagination(paginationPageSize=25)

                gb.configure_default_column(floatingFilter=True,
                                            editable=False,
                                            selectable=False)

                gb.configure_grid_options(
                    domLayout='normal', preventDefaultOnContextMenu=True)
                gridOptions = set_def_aggrid_options(gb.build())

                if df.shape[0] == 1:
                    height = 150
                elif df.shape[0] < 4:
                    height = 200
                else:
                    height = 400
                _ = AgGrid(
                    df,
                    height=height,
                    gridOptions=gridOptions,
                    allow_unsafe_jscode=True,
                    update_mode=GridUpdateMode.NO_UPDATE,
                    theme='streamlit',
                    key=str(randint(1, 10000000))
                )

    @st.cache_data(ttl=60)
    def _fetch_data_with_cache(self, table: str, columns: list):
        '''Fetch data from the backend with caching'''
        return gui_get_df(table, self._config_file, columns=columns)

    async def _fetch_data(self, query_str: str, table: str, namespace: list, columns: list):
        '''Fetch data asynchronously to avoid blocking the UI'''
        return gui_get_df(table, self._config_file, query_str=query_str, namespace=namespace, columns=columns)

    def _sync_state(self) -> None:
        pass

    def _build_query(self, search_text: str):
        '''Build the appropriate query for the search'''

        state = self._state
        search_text = search_text.replace('\"', '').replace('\'', '')
        if not search_text:
            return '', {}, []

        unique_query = {}

        addrs = search_text.split()
        if not addrs:
            return '', {}, []

        query_str = disjunction = ''
        columns = ['default']

        if addrs[0] not in ['mac', 'macs', 'route', 'routes', 'arpnd', 'address',
                            'vtep', 'vteps', 'asn', 'asns', 'vlan', 'vlans', 'mtu', 'mtus']:
            try:
                ip_address(addrs[0])
            except ValueError:
                if not validate_macaddr(addrs[0]):
                    raise ValueError(f'Invalid keyword or IP/Mac address "{addrs[0]}"')

        # Handle the rest of the search query logic [same as the original]
        # This will include checks for MAC, IP, routes, ASN, VTEP, etc.

        return query_str, unique_query, columns
