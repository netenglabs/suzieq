from collections import deque
from dataclasses import dataclass, field
from ipaddress import ip_address

import streamlit as st
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode

from suzieq.shared.utils import convert_macaddr_format_to_colon
from suzieq.gui.stlit.guiutils import (gui_get_df,
                                       SuzieqMainPages)
from suzieq.gui.stlit.pagecls import SqGuiPage


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


class SearchPage(SqGuiPage):
    '''Page for Path trace page'''
    _title: str = SuzieqMainPages.SEARCH.value
    _state = SearchSessionState()

    @property
    def add_to_menu(self):
        return True

    def build(self):
        self._get_state_from_url()
        self._create_sidebar()
        layout = self._create_layout()
        self._render(layout)
        self._save_page_url()

    def _create_sidebar(self) -> None:

        state = self._state
        devdf = gui_get_df('device', columns=['namespace', 'hostname'])
        if devdf.empty:
            st.error('Unable to retrieve any namespace info')
            st.stop()

        namespaces = [''] + sorted(devdf.namespace.unique().tolist())
        if not state.namespace:
            nsidx = 0
        else:
            nsidx = namespaces.index(state.namespace)
        namespace = st.sidebar.selectbox('Namespace',
                                         namespaces, key='search_ns',
                                         index=nsidx,
                                         on_change=self._sync_state)

        st.sidebar.markdown(
            """Displays last 5 search results.

You can use search to find specific objects. You can qualify what you're
searching for by qualifying the search term with the type. We support:
- __addresses__: You can qualify a specific table to look for the address.
                 The search string can start with one of the following
                 keywords: __route, mac, arpnd__, to specify which table you
                 want the search to be performed in . If you don't specify a
                 table name, we assume ```network find``` to search for the
                 network attach point for the address. For example,
                 ```arpnd 172.16.1.101``` searches for entries with
                 172.16.1.101 in the IP address column of the arpnd table.
                 Similarly, ```10.0.0.21``` searches for where in the
                 network that IP address is attached to.
- __ASN__: Start the search with the string ```asn``` followed by the ASN
           number. Typing ```asns``` will show you the list of unique ASNs
               across the specified namespaces.
- __VTEP__: Start the search with the string ```vtep``` followed by the VTEP
            IP address. Typing ```vteps``` will show you the list of unique
            VTEPs across the specified namespaces.
- __VNI__: Start the search with the string ```vni``` followed by the VNI
           number.
Typing ```mtus``` will show you the list of unique MTUs across the
specified namespaces.

When specifying a table, you can specify multiple addresses to look for by
 providing the addresses as a space separated values such as
 ```"172.16.1.101 10.0.0.11"``` or
  ```mac "00:01:02:03:04:05 00:21:22:23:24:25"```
  and so on. A combination of mac and IP address can also be specified with
   the address table. Support for more sophisticated search will be added in
    the next few releases.
    """)

        if namespace != state.namespace:
            state.namespace = namespace

    def _create_layout(self) -> dict:
        return {
            'current': st.empty()
        }

    def _render(self, layout) -> None:

        state = self._state
        search_text = st.session_state.search_text
        query_str, uniq_dict, columns = self._build_query(search_text)

        if state.namespace:
            query_ns = [state.namespace]
        else:
            query_ns = []

        if query_str:
            if state.table == "network":
                df = gui_get_df(state.table,
                                verb='find',
                                namespace=query_ns,
                                view="latest", columns=columns,
                                address=query_str)
            else:
                df = gui_get_df(state.table,
                                namespace=query_ns, query_str=query_str,
                                view="latest", columns=columns)
                if not df.empty:
                    df = df.query(query_str) \
                        .drop_duplicates() \
                        .reset_index(drop=True)

            expander = layout['current'].expander(f'Search for {search_text}',
                                                  expanded=True)
            with expander:
                if not df.empty:
                    self._draw_aggrid_df(df)
                else:
                    st.info('No matching result found')
        elif uniq_dict:
            columns = ['namespace'] + uniq_dict['column']
            df = gui_get_df(uniq_dict['table'],
                            namespace=query_ns, view='latest', columns=columns)
            if not df.empty:
                df = df.groupby(by=columns).first().reset_index()

            expander = layout['current'].expander(f'Search for {search_text}',
                                                  expanded=True)
            with expander:
                if not df.empty:
                    self._draw_aggrid_df(df)
                else:
                    st.info('No matching result found')
        elif len(state.prev_results) == 0:
            st.info('Enter a search string to see results')

        for prev_res in reversed(state.prev_results):
            psrch, prev_df = prev_res
            if psrch == search_text:
                continue
            expander = st.expander(f'Search for {psrch}', expanded=True)
            with expander:
                if not prev_df.empty:
                    self._draw_aggrid_df(prev_df)
                else:
                    st.info('No matching result found')

        if ((query_str or uniq_dict) and
                (search_text != state.search_text)):
            state.prev_results.append((search_text, df))
            state.search_text = search_text

    def _draw_aggrid_df(self, df):

        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(paginationPageSize=25)

        gb.configure_default_column(floatingFilter=True, editable=False)

        gb.configure_grid_options(
            domLayout='normal', preventDefaultOnContextMenu=True)
        gridOptions = gb.build()

        _ = AgGrid(
            df,
            gridOptions=gridOptions,
            allow_unsafe_jscode=True,
            update_mode=GridUpdateMode.NO_UPDATE,
            theme='streamlit',
        )

    def _sync_state(self) -> None:
        pass

    # pylint: disable=too-many-statements
    def _build_query(self, search_text: str) -> str:
        '''Build the appropriate query for the search'''

        state = self._state
        if not search_text:
            return '', '', []

        unique_query = {}

        addrs = search_text.split()
        if not addrs:
            return '', '', []

        query_str = disjunction = ''
        columns = ['default']

        if addrs[0].startswith('mac'):
            state.table = 'macs'
            addrs = addrs[1:]
        elif addrs[0].startswith('route'):
            state.table = 'routes'
            addrs = addrs[1:]
        elif addrs[0].startswith('arp'):
            state.table = 'arpnd'
            addrs = addrs[1:]
        elif addrs[0].startswith('address'):
            state.table = 'network'
            search_text = ' '.join(addrs[1:])
        elif addrs[0].startswith('vtep'):
            state.table = 'evpnVni'
            if addrs[0] != 'vteps':
                query_str = (f'priVtepIp.isin({addrs[1:]}) or '
                             f'secVtepIp.isin({addrs[1:]})')
                columns = ['namespace', 'hostname', 'priVtepIp',
                           'secVtepIp']
        elif addrs[0].startswith('vni'):
            state.table = 'evpnVni'
            if addrs[0] == 'vnis':
                try:
                    vnis = [int(x) for x in addrs[1:]]
                except ValueError:
                    vnis = []
                query_str = f'vni.isin({vnis})'
                columns = ['namespace', 'hostname', 'vni']
        elif addrs[0].startswith('asn'):
            state.table = 'bgp'
            if addrs[0] != "asns":
                try:
                    asns = [int(x) for x in addrs[1:]]
                except ValueError:
                    asns = []
                query_str = f'asn.isin({asns})'
                columns = ['namespace', 'hostname', 'asn']
        elif addrs[0].startswith('vlan'):
            state.table = 'vlan'
            if addrs[0] != "vlans":
                try:
                    vlans = [int(x) for x in addrs[1:]]
                except ValueError:
                    vlans = []
                query_str = f'vlan.isin({vlans})'
                columns = ['namespace', 'hostname', 'vlan']
        elif addrs[0].startswith('mtus'):
            state.table = 'interface'
            if addrs[0] != "mtus":
                try:
                    mtus = [int(x) for x in addrs[1:]]
                except ValueError:
                    mtus = []
                query_str = f'mtu.isin({mtus})'
                columns = ['namespace', 'hostname', 'mtu']
        else:
            state.table = 'network'

        if state.table == 'network':
            return search_text, unique_query, columns

        for addr in addrs:
            if addr.lower() == 'vteps':
                unique_query = {'table': 'evpnVni',
                                'column': ['priVtepIp', 'secVtepIp'],
                                'colname': 'vteps'}
            elif addr.lower() == 'vnis':
                unique_query = {'table': 'evpnVni',
                                'column': ['vni'], 'colname': 'vnis'}
            elif addr.lower() == 'asns':
                unique_query = {'table': 'bgp', 'column': ['asn', 'peerAsn'],
                                'colname': 'asns'}
            elif addr.lower() == 'vlans':
                unique_query = {'table': 'vlan', 'column': ['vlan'],
                                'colname': 'vlans'}
            elif addr.lower() == 'mtus':
                unique_query = {'table': 'interfaces', 'column': ['mtu'],
                                'colname': 'mtus'}

            elif '::' in addr:
                if state.table == 'arpnd':
                    query_str += f' {disjunction} ipAddress == "{addr}" '
                elif state.table == 'routes':
                    query_str += f'{disjunction} prefix == "{addr}" '
                else:
                    query_str += f' {disjunction} ' \
                        f'ip6AddressList.str.startswith("{addr}/") '
            elif ':' in addr and state.table in ['macs', 'arpnd']:
                query_str += f' {disjunction} macaddr == "{addr}" '
            else:
                try:
                    addr = ip_address(addr)
                    macaddr = None
                except ValueError:
                    macaddr = convert_macaddr_format_to_colon(addr)
                    addr = None

                if state.table == "macs":
                    query_str = f'{disjunction} macaddr == "{macaddr}" '
                elif state.table == 'arpnd':
                    if addr:
                        query_str += f' {disjunction} ipAddress == "{addr}" '
                    elif macaddr:
                        query_str += f' {disjunction} macaddr == "{macaddr}" '
                elif state.table == 'routes':
                    query_str += f'{disjunction} prefix == "{addr}" '
                else:
                    query_str = ''

            if not disjunction:
                disjunction = 'or'

        state.query_str = query_str
        state.unique_query = unique_query
        return query_str, unique_query, columns
