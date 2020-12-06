from collections import deque
from dataclasses import dataclass

import pandas as pd
import streamlit as st
from suzieq.sqobjects.path import PathObj
import suzieq.gui.SessionState as SessionState


@dataclass
class SearchSessionState:
    search_str: str = ''
    past_df = None
    table: str = ''
    query_str: str = ''
    prev_results = deque()


def get_title():
    return 'Search'


@st.cache(ttl=90, allow_output_mutation=True)
def search_get_df(sqobject, **kwargs):
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


def build_query(state: SessionState, search_text: str) -> str:
    '''Build the appropriate query for the search'''

    if not search_text:
        return ''

    addrs = search_text.split()
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
    else:
        state.table = 'address'

    if state.table == 'address':
        return search_text

    query_str = disjunction = ''
    for addr in addrs:
        if '::' in addr:
            if state.table == 'arpnd':
                query_str += f' {disjunction} ipAddress == "{addr}" '
            elif state.table == 'routes':
                query_str += f'{disjunction} prefix == "{addr}" '
            else:
                query_str += f' {disjunction} ip6AddressList.str.startswith("{addr}/") '
        elif ':' in addr:
            query_str += f' {disjunction} macaddr == "{addr}" '
        else:
            if state.table == 'arpnd':
                query_str += f' {disjunction} ipAddress == "{addr}" '
            elif state.table == 'routes':
                query_str += f'{disjunction} prefix == "{addr}" '
            else:
                query_str += f' {disjunction} ipAddressList.str.startswith("{addr}/") '

        if not disjunction:
            disjunction = 'or'

    state.query_str = query_str
    return query_str


def search_sidebar(state, page_flip: bool):
    '''Draw the sidebar'''

    st.sidebar.markdown(
        "Displays last 5 search results")


def init_state(state_container: SessionState) -> SearchSessionState:
    '''Initialize the page's session state'''

    state_container.pathSessionState = state = SearchSessionState()

    return state


def page_work(state_container: SessionState, page_flip: bool):
    '''Main page workhorse'''

    if hasattr(state_container, 'searchSessionState'):
        state = getattr(state_container, 'searchSessionState')
    else:
        state = init_state(state_container)

    search_sidebar(state, page_flip)

    query_str = build_query(state, state_container.search_text)

    if query_str:
        if state.table == "address":
            df = search_get_df(state_container.sqobjs[state.table],
                               view="latest", columns=['default'],
                               address=query_str.split())
        else:
            df = search_get_df(state_container.sqobjs[state.table],
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

    for prev_res in state.prev_results:
        psrch, prev_df = prev_res
        expander = st.beta_expander(f'Search for {psrch}', expanded=True)
        with expander:
            if not prev_df.empty:
                st.dataframe(prev_df)
            else:
                st.info('No matching result found')

    if state_container.search_text:
        state.prev_results.append((state_container.search_text, df))
