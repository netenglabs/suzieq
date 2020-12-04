from dataclasses import dataclass
from typing import List
from importlib import resources
from types import ModuleType

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

    page_tbl = {}
    module_list = globals()
    for key in module_list:
        if isinstance(module_list[key], ModuleType):
            if module_list[key].__package__ == 'suzieq.gui.pages':
                objlist = list(filter(lambda x: x.endswith('_run'),
                                      dir(module_list[key])))
                for obj in objlist:
                    page_tbl[key] = getattr(module_list[key], obj)

    return page_tbl


def apprun():
    '''The main application routine'''

    state = SessionState.get(prev_page='', path_vrf='', path_namespace='',
                             path_source='', path_dest='', path_run=False,
                             overview_add_vlans=False, overview_add_macs=False,
                             overview_add_vrfs=False,
                             overview_add_routes=False, main_page='',
                             xna_sidebar_key=0,
                             xna_namespace='', xna_hostname='', xna_table='',
                             xna_view='', xna_columns=['default'],
                             xna_query='', xna_uniq_clicked=0,
                             xna_assert_clicked=False)

    st.set_page_config(layout="wide")
    hide_st_index()
    pages = build_pages()
    # These three are hardcoded to preserve order
    pagelist = ['Overview', 'XNA', 'Path']
    for key in pages:
        if key not in pagelist:
            pagelist.append(key)
    page = display_title(pagelist)
    if page != state.prev_page:
        page_flip = True
        state.prev_page = page
    else:
        page_flip = False
    horizontal_radio()

    if page in pages:
        pages[page](state, page_flip)


if __name__ == '__main__':
    apprun()
