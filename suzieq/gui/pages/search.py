from collections import deque
from dataclasses import dataclass, asdict, field
from typing import List

import pandas as pd
import streamlit as st
from suzieq.gui.guiutils import gui_get_df


def get_title():
    # suzieq_gui.py has hardcoded this name.
    return 'Search'


@dataclass
class SearchSessionState:
    search_text: str = ''
    past_df = None
    table: str = ''
    nsidx: int = -1
    query_str: str = ''
    unique_query: dict = field(default_factory=dict)
    prev_results = deque(maxlen=5)


def build_query(state, search_text: str) -> str:
    '''Build the appropriate query for the search'''

    if not search_text:
        return '', ''

    unique_query = {}

    addrs = search_text.split()
    if not addrs:
        return '', ''

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
        state.table = 'address'
        search_text = ' '.join(addrs[1:])
    elif addrs[0].startswith('vtep'):
        state.table = 'evpnVni'
    elif addrs[0].startswith('vni'):
        state.table = 'evpnVni'
    elif addrs[0].startswith('asn'):
        state.table = 'bgp'
    elif addrs[0].startswith('vlan'):
        state.table = 'vlan'
    elif addrs[0].startswith('mtus'):
        state.table = 'interface'
    else:
        state.table = 'address'

    if state.table == 'address':
        return search_text, unique_query

    query_str = disjunction = ''

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
                query_str += \
                    f' {disjunction} ip6AddressList.str.startswith("{addr}/") '
        elif ':' in addr and state.table in ['macs', 'arpnd', 'address']:
            query_str += f' {disjunction} macaddr == "{addr}" '
        else:
            if state.table == 'arpnd':
                query_str += f' {disjunction} ipAddress == "{addr}" '
            elif state.table == 'routes':
                query_str += f'{disjunction} prefix == "{addr}" '
            elif state.table == 'address':
                query_str += \
                    f' {disjunction} ipAddressList.str.startswith("{addr}/") '

        if not disjunction:
            disjunction = 'or'

    state.query_str = query_str
    state.unique_query = unique_query
    return query_str, unique_query


def search_sidebar(state, sqobjs):
    '''Draw the sidebar'''

    devdf = gui_get_df(sqobjs['device'], columns=['namespace', 'hostname'])
    if devdf.empty:
        st.error('Unable to retrieve any namespace info')
        st.stop()

    namespaces = [''] + sorted(devdf.namespace.unique().tolist())
    if state.nsidx == -1:
        nsidx = 0
    else:
        nsidx = state.nsidx
    namespace = st.sidebar.selectbox('Namespace',
                                     namespaces, index=nsidx)

    st.sidebar.markdown(
        """Displays last 5 search results.

The search string can start with one of the following keywords: __address, route, mac, arpnd__, to specify which table you want the search to be performed in . If you don't specify a table name, address is assumed. For example, ```arpnd 172.16.1.101``` searches for entries with 172.16.1.101 in the IP address column of the arpnd table. Similarly, ```10.0.0.21``` searches for that IP address in the address table.

__In this initial release, you can only search for an IP address or MAC address__ in one of those tables. You can specify multiple addresses to look for by providing the addresses as a space separated values such as ```172.16.1.101 10.0.0.11``` or ```mac 00:01:02:03:04:05 00:21:22:23:24:25``` and so on. A combination of mac and IP address can also be specified. Obviously the combination doesn't apply to tables such as routes and macs. Support for more sophisticated search will be added in the next few releases.
""")

    nsidx = namespaces.index(namespace)
    if nsidx != state.nsidx:
        state.nsidx = nsidx

    return namespace


def page_work(state_container, page_flip: bool):
    '''Main page workhorse'''

    if not state_container.searchSessionState:
        state_container.searchSessionState = SearchSessionState()

    state = state_container.searchSessionState

    namespace = search_sidebar(state, state_container.sqobjs)

    query_str, uniq_dict = build_query(state,
                                       state_container.search_text)
    if namespace:
        query_ns = [namespace]
    else:
        query_ns = []
    if query_str:
        if state.table == "address":
            df = gui_get_df(state_container.sqobjs[state.table],
                            namespace=query_ns,
                            view="latest", columns=['default'],
                            address=query_str.split())
        else:
            df = gui_get_df(state_container.sqobjs[state.table],
                            namespace=query_ns,
                            view="latest", columns=['default'])
            if not df.empty:
                df = df.query(query_str).reset_index(drop=True)

        expander = st.beta_expander(f'Search for {state_container.search_text}',
                                    expanded=True)
        with expander:
            if not df.empty:
                st.dataframe(df)
            else:
                st.info('No matching result found')
    elif uniq_dict:
        columns = ['namespace'] + uniq_dict['column']
        df = gui_get_df(state_container.sqobjs[uniq_dict['table']],
                        namespace=query_ns, view='latest', columns=columns)
        if not df.empty:
            df = df.groupby(by=columns).first().reset_index()

        expander = st.beta_expander(f'Search for {state_container.search_text}',
                                    expanded=True)
        with expander:
            if not df.empty:
                st.dataframe(df)
            else:
                st.info('No matching result found')

    for count, prev_res in enumerate(reversed(state.prev_results)):
        psrch, prev_df = prev_res
        if psrch == state_container.search_text:
            continue
        expander = st.beta_expander(f'Search for {psrch}', expanded=True)
        with expander:
            if not prev_df.empty:
                st.dataframe(prev_df)
            else:
                st.info('No matching result found')

    if ((query_str or uniq_dict) and
            (state_container.search_text != state.search_text)):
        state.prev_results.append((state_container.search_text, df))
        state.search_text = state_container.search_text

    st.experimental_set_query_params(**asdict(state))
