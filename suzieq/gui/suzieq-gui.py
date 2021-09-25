from suzieq.sqobjects import *
from suzieq.gui.pages import *
from suzieq.gui.guiutils import (get_image_dir, display_title,
                                 get_main_session_by_id, SuzieqMainPages)
import streamlit as st
from streamlit import caching
from types import ModuleType
from collections import defaultdict
import base64


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


def build_sqobj_table() -> dict:
    '''Build available list of suzieq table objects'''

    sqobj_tables = {}
    module_list = globals()
    blacklisted_tables = ['path', 'topmem', 'topcpu', 'ifCounters', 'topology',
                          'time']
    for key in module_list:
        if isinstance(module_list[key], ModuleType):
            if key in blacklisted_tables:
                continue
            if module_list[key].__package__ == 'suzieq.sqobjects':
                objlist = list(filter(lambda x: x.endswith('Obj'),
                                      dir(module_list[key])))
                for obj in objlist:
                    sqobj_tables[key] = getattr(module_list[key], obj)

    return sqobj_tables


def apprun():
    '''The main application routine'''

    st.set_page_config(layout="wide", page_title="Suzieq")

    state = st.session_state
    for key, val in [('pages', None),
                     ('pagelist', []),
                     ('page', None),
                     ('search_text', ''),
                     ('sqobjs', {})]:
        if key not in state:
            state[key] = val

    if not state.pages:
        state.pages = build_pages()
        state.sqobjs = build_sqobj_table()
        # Hardcoding the order of these three
        state.pagelist = [SuzieqMainPages.STATUS.value,
                          SuzieqMainPages.XPLORE.value,
                          SuzieqMainPages.PATH.value,
                          SuzieqMainPages.SEARCH.value]
        for pg in state.pages:
            if pg not in state.pagelist:
                state.pagelist.append(pg)

    url_params = st.experimental_get_query_params()
    if url_params.get('page', ''):
        page = url_params['page']
        if isinstance(page, list):
            page = page[0]

        old_session_state = get_main_session_by_id(
            url_params.get('session', [''])[0])
        if page == "_Path_Debug_":
            state.pages[page](old_session_state, True)
            st.stop()
        elif page == "_Help_":
            state.pages[page](old_session_state, None)
            st.stop()
        if isinstance(page, list):
            page = page[0]
    else:
        page = None

    if page is None:
        if state.page:
            page = state.page
        else:
            page = state.pagelist[0]

    state.page = page

    page, search_text = display_title(page)

    if search_text != state.search_text:
        state.search_text = search_text
        state.page = page = 'Search'

    state.pages[page](state)


if __name__ == '__main__':
    apprun()
