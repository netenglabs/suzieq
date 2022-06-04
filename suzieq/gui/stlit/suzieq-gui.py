import os
import sys
from collections import defaultdict
import base64
from typing import Dict

import streamlit as st

from suzieq.gui.stlit.guiutils import (SUZIEQ_COLOR, get_image_dir,
                                       get_main_session_by_id, SuzieqMainPages)
from suzieq.gui.stlit.pagecls import SqGuiPage
from suzieq.version import SUZIEQ_VERSION
from suzieq.shared.utils import sq_get_config_file


def set_horizontal_radio():
    '''Make the radio buttons horizontal'''
    st.write('<style>div.row-widget.stRadio > '
             'div{flex-direction:row;}</style>',
             unsafe_allow_html=True)


def set_vertical_radio():
    '''Make the radio buttons horizontal'''
    st.write('<style>div.row-widget.stRadio > '
             'div{flex-direction:column;}</style>',
             unsafe_allow_html=True)


def display_help_icon(url: str):
    '''Display Help Icon with click to take you to appropriate page'''

    help_img = f'{get_image_dir()}/helps.png'
    with open(help_img, "rb") as f:
        img = base64.b64encode(f.read()).decode()

    st.sidebar.markdown(
        f'<a target="_help" href="{url}"><img class="help-img" '
        f'src="data:image/png;base64,'
        f'{img}"></a>',
        unsafe_allow_html=True)


def display_title(page: str):
    '''Render the logo and the app name'''

    state = st.session_state
    menulist = state.menulist
    search_text = state.search_text

    LOGO_IMAGE = f'{get_image_dir()}/logo-small.jpg'
    st.markdown(
        """
        <style>
            .logo-container {
                display: flex;
            }
            .logo-text {
                color: %s;
            }
            .logo-img {
                max-height: 7.5em;
                margin-bottom: 1em;
                float:right;
            }
            @media(max-width: 960px){
                .logo-container {
                    justify-content: center;
                }
                .logo-text {
                    display: none;
                }
            }
            @media(max-width: 640px){
                .logo-text {
                    display: inline;
                }
            }
        </style>
        """ % (SUZIEQ_COLOR),
        unsafe_allow_html=True
    )

    title_col, _, page_col, srch_col = st.columns([2, 1, 2, 2])

    with open(LOGO_IMAGE, "rb") as f:
        img = base64.b64encode(f.read()).decode()

    with title_col:
        st.markdown(
            f"""
            <div class="logo-container">
                <img class="logo-img" src="data:image/png;base64,
                {img}">
                <h1 class='logo-text'>Suzieq</h1>
            </div>
            """,
            unsafe_allow_html=True
        )

    sel_menulist = list(filter(lambda x: not x.startswith('_'), menulist))

    with srch_col:
        st.text(' ')
        search_str = st.text_input("Search", value=state.search_text,
                                   key='search', on_change=main_sync_state)
    if search_text is not None and (search_str != search_text):
        # We're assuming here that the page is titled Search
        page = 'Search'

    with page_col:
        # The empty writes are for aligning the pages link with the logo
        st.text(' ')
        set_horizontal_radio()
        st.radio('Page', sel_menulist, key='sq_page',
                 index=sel_menulist.index(page or 'Status'),
                 on_change=main_sync_state)
        page = state.sq_page

    return page, search_str


def main_sync_state():
    '''Sync search & page state on main Suzieq GUI page'''
    wsstate = st.session_state

    if wsstate.search_text != wsstate.search:
        wsstate.search_text = wsstate.search
        wsstate.page = wsstate.sq_page = 'Search'

    if wsstate.page != wsstate.sq_page:
        wsstate.page = wsstate.sq_page
        st.experimental_set_query_params(**{'page': wsstate.page})
        if wsstate.page != 'Search':
            wsstate.search_text = ''


def build_pages() -> Dict:
    '''Build dict of page name and corresponding module'''

    pages = SqGuiPage.get_plugins()
    page_tbl = defaultdict(dict)

    for obj in pages.values():
        page = obj()
        page_tbl[page._title] = page

    return page_tbl


# pylint: disable=too-many-statements
def apprun(*args):
    '''The main application routine'''

    if not args:
        args = sys.argv

    config_file = os.environ.get('SQ_GUI_CONFIG_FILE', '')
    config_file = sq_get_config_file(config_file)

    state = st.session_state
    state.config_file = config_file

    st.set_page_config(
        layout="wide",
        page_title="Suzieq",
        menu_items={
            'Get Help': 'https://suzieq.readthedocs.io/',
            'Report a bug':
            'https://github.com/netenglabs/suzieq/issues/new/choose',
            'About': f'''
            Suzieq Version: {SUZIEQ_VERSION}.
            Copyright 2022 Stardust Systems Inc. All Rights Reserved
            '''
        })

    for key, val in [('pages', None),
                     ('menulist', []),
                     ('page', None),
                     ('search_text', ''),
                     ('sqobjs', {})]:
        if key not in state:
            state[key] = val

    if not state.menulist:
        state.pages = build_pages()
        # Hardcoding the order of these pages
        state.menulist = [SuzieqMainPages.STATUS.value,
                          SuzieqMainPages.XPLORE.value,
                          SuzieqMainPages.PATH.value,
                          SuzieqMainPages.SEARCH.value]
        for pg, obj in state.pages.items():
            if pg not in state.menulist and obj.add_to_menu:
                state.menulist.append(pg)

    # NOTE: Do not move this before set_page_config
    if 'first_time' not in state:
        state.first_time = True

    url_params = st.experimental_get_query_params()
    if url_params.get('page', ''):
        page = url_params['page']
        if isinstance(page, list):
            page = page[0]
        old_session_state = get_main_session_by_id(
            url_params.get('session', [''])[0])
        if old_session_state:
            if page == "Path-Debug":
                state.pages[page].set_path_state(old_session_state)
                state.pages[page].build()
                st.stop()
            elif page == "Help":
                state.pages[page].build()
                st.stop()

        if page == 'Search' and state.first_time:
            search_text = url_params.get('search_text', '')
            if search_text:
                state.search_text = search_text[0]

        if isinstance(page, list):
            page = page[0]
    else:
        page = None

    if page is None:
        if state.page:
            page = state.page
        else:
            page = state.menulist[0]

    state.page = page

    page, search_text = display_title(page)
    state.first_time = False

    if search_text != state.search_text:
        state.search_text = search_text
        state.page = page = 'Search'

    state.pages[page].build()


if __name__ == '__main__':
    apprun()
