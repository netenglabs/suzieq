from types import ModuleType
from collections import defaultdict
import base64

import streamlit as st

from suzieq.gui.session_state import get_session_state
from suzieq.gui.pages import *
from suzieq.sqobjects import *


def display_title(page, pagelist):
    '''Render the logo and the app name'''

    LOGO_IMAGE = 'logo-small.jpg'
    st.markdown(
        """
        <style>
        .container {
            display: flex;
        }
        .logo-text {
            font-weight:700 !important;
            font-size:24px !important;
            color: purple !important;
            padding-top: 40px !important;
        }
        .logo-img {
            width: 20%;
            height: auto;
            float:right;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    title_col, mid, page_col, srch_col = st.beta_columns([2, 1, 2, 2])
    with title_col:
        st.markdown(
            f"""
            <div class="container">
                <img class="logo-img" src="data:image/png;base64,{base64.b64encode(open(LOGO_IMAGE, "rb").read()).decode()}">
                <h1 style='color:purple;'>Suzieq</h1>
            </div>
            """,
            unsafe_allow_html=True
        )
    with page_col:
        # The empty writes are for aligning the pages link with the logo
        st.text(' ')
        srch_holder = st.empty()
        pageidx = 0 if not page else pagelist.index(page)
        page = srch_holder.selectbox('Page', pagelist, index=pageidx)

    with srch_col:
        st.text(' ')
        search_text = st.text_input("Address Search", "")
    if search_text:
        # We're assuming here that the page is titled Search
        srchidx = pagelist.index('Search')
        page = srch_holder.selectbox('Page', pagelist, index=srchidx)
    return page, search_text


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

    state = get_session_state()
    # state = SessionState.get(pages=None, prev_page='', search_text='',
    #                          sqobjs={})

    st.set_page_config(layout="wide", page_title="Suzieq")

    if not state.pages:
        state.pages = build_pages()
        state.sqobjs = build_sqobj_table()

    url_params = st.experimental_get_query_params()
    if url_params.get('page', ''):
        page = url_params['page']
        if isinstance(page, list):
            page = page[0]
    else:
        page = None

    # Hardcoding the order of these three
    pagelist = ['Status', 'Xplore', 'Path', 'Search']
    for pg in state.pages:
        if pg not in pagelist:
            pagelist.append(pg)

    page, search_text = display_title(page, pagelist)

    if state.search_text is None:
        state.search_text = ''

    if search_text != state.search_text:
        page = 'Search'
        state.search_text = search_text

    if state.prev_page != page:
        page_flip = True
    else:
        page_flip = False
    state.prev_page = page

    state.pages[page](state, page_flip)
    if page not in ['Search', 'Status']:
        state.sync()


if __name__ == '__main__':
    apprun()
