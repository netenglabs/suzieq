from dataclasses import dataclass
from typing import List
from importlib import resources
from types import ModuleType
from collections import defaultdict

import streamlit as st


from suzieq.gui.guiutils import horizontal_radio, display_title, hide_st_index
import suzieq.gui.SessionState as SessionState
from suzieq.gui.pages import *


@dataclass
class SidebarData:
    '''Class for returning data from the sidebar'''
    namespace: str
    hostname: str
    table: str
    view: str
    query: str
    assert_clicked: bool
    columns: List[str]


def build_pages():
    '''Build the pages and the corresponding functions to be called'''

    page_tbl = defaultdict(dict)
    module_list = globals()
    for key in module_list:
        if isinstance(module_list[key], ModuleType):
            if module_list[key].__package__ == 'suzieq.gui.pages':
                objlist = filter(
                    lambda x: x == "page_work" or x == "get_title",
                    dir(module_list[key]))
                page_name = None
                for obj in objlist:
                    if obj == 'get_title':
                        page_name = getattr(module_list[key], obj)()
                    else:
                        work_fn = getattr(module_list[key], obj)
                if page_name:
                    page_tbl[page_name] = work_fn

    return page_tbl


def build_xna_query(state: SessionState, search_text: str):
    '''Build the appropriate query for the search'''

    addrs = search_text.split()
    if addrs[0].startswith('mac'):
        state.xna_table = 'macs'
        addrs = addrs[1:]
    elif addrs[0].startswith('route'):
        state.xna_table = 'routes'
        addrs = addrs[1:]
    elif addrs[0].startswith('arp'):
        state.xna_table = 'arpnd'
        addrs = addrs[1:]
    else:
        state.xna_table = 'address'

    query_str = disjunction = ''
    for addr in addrs:
        if '::' in addr:
            if state.xna_table == 'arpnd':
                query_str += f' {disjunction} ipAddress == "{addr}" '
            elif state.xna_table == 'routes':
                query_str += f'{disjunction} prefix == "{addr}" '
            else:
                query_str += f' {disjunction} ip6AddressList.str.startswith("{addr}/") '
        elif ':' in addr:
            query_str += f' {disjunction} macaddr == "{addr}" '
        else:
            if state.xna_table == 'arpnd':
                query_str += f' {disjunction} ipAddress == "{addr}" '
            elif state.xna_table == 'routes':
                query_str += f'{disjunction} prefix == "{addr}" '
            else:
                query_str += f' {disjunction} ipAddressList.str.startswith("{addr}/") '

        if not disjunction:
            disjunction = 'or'

    state.xna_query = query_str
    state.prev_page = "Overview"  # Any page we want to set the page_flip marker
    return


def apprun():
    '''The main application routine'''

    state = SessionState.get(pages=None, prev_page='')

    st.set_page_config(layout="wide")
    hide_st_index()

    if not state.pages:
        state.pages = build_pages()

    # Hardcoding the order of these three
    pagelist = ['Status', 'Xplore', 'Path']
    for page in state.pages:
        if page not in pagelist:
            pagelist.append(page)

    page, search_text = display_title(pagelist)
    if search_text:
        page = 'XNA'
        build_xna_query(state, search_text)

    if page != state.prev_page:
        page_flip = True
        state.prev_page = page
    else:
        page_flip = False
    horizontal_radio()

    state.pages[page](state, page_flip)


if __name__ == '__main__':
    apprun()
