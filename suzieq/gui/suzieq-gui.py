from importlib.util import find_spec
from importlib import import_module
from collections import defaultdict

import streamlit as st

from suzieq.gui.guiutils import (display_title,
                                 get_main_session_by_id, SuzieqMainPages)
from suzieq.version import SUZIEQ_VERSION


def build_pages():
    '''Build dict of page name and corresponding module'''

    page_tbl = defaultdict(dict)
    module_list = find_spec('suzieq.gui.pages').loader.contents()
    for entry in module_list:
        if entry.startswith('__'):
            continue
        if entry.endswith('.py'):
            entry = entry[:-3]
        mod = import_module(f'suzieq.gui.pages.{entry}')
        page_fn = getattr(mod, 'get_title', None)
        if page_fn:
            page_name = page_fn()
            work_fn = getattr(mod, 'page_work', None)
            if work_fn:
                page_tbl[page_name] = work_fn

    return page_tbl


def apprun():
    '''The main application routine'''

    st.set_page_config(layout="wide",
                       page_title="Suzieq",
                       menu_items={
                           'About': f'Suzieq Version: {SUZIEQ_VERSION}'
                       })

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
        # Hardcoding the order of these pages
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
        if old_session_state:
            if page == "_Path_Debug_":
                state.pages[page](old_session_state)
                st.stop()
            elif page == "_Help_":
                state.pages[page](old_session_state)
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
