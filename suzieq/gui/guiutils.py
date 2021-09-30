from importlib.util import find_spec
import os
import base64
from enum import Enum

import streamlit as st
import pandas as pd
from streamlit.elements.select_slider import SelectSliderMixin
from streamlit.server.server import Server
from streamlit.report_thread import get_report_ctx


class SuzieqMainPages(str, Enum):
    STATUS = "Status"
    XPLORE = "Xplore"
    PATH = "Path"
    SEARCH = "Search"


@st.cache(ttl=90, allow_output_mutation=True, show_spinner=False,
          max_entries=20)
def gui_get_df(sqobject, verb: str = 'get', **kwargs) -> pd.DataFrame:
    """Get the cached value of the table provided

    The only verbs supported are get and find.

    Args:
        sqobject ([type]): The sqobject for which to get the data
        verb (str, optional): . Defaults to 'get'.

    Returns:
        [pandas.DataFrame]: The dataframe

    Raises:
        ValueError: If the verb is not supported
    """
    table = kwargs.pop('_table', '')
    view = kwargs.pop('view', 'latest')
    columns = kwargs.pop('columns', ['default'])
    stime = kwargs.pop('start_time', '')
    etime = kwargs.pop('end_time', '')

    if columns == ['all']:
        columns = ['*']
    if verb == 'get':
        df = sqobject(view=view, start_time=stime, end_time=etime) \
            .get(columns=columns, **kwargs)
    elif verb == 'find':
        df = sqobject(view=view, start_time=stime, end_time=etime) \
            .find(**kwargs)
    else:
        raise ValueError(f'Unsupported verb {verb}')

    if not df.empty:
        df = sqobject().humanize_fields(df)
        if table == 'address':
            if 'ipAddressList' in df.columns:
                df = df.explode('ipAddressList').fillna('')
            if 'ip6AddressList' in df.columns:
                df = df.explode('ip6AddressList').fillna('')
    if not (columns == ['*'] or columns == ['default']):
        return df[columns].reset_index(drop=True)
    return df.reset_index(drop=True)


def get_base_url():
    '''Return the base URL of the page.
    Usually connections are http://localhost:8501. But the port can change
    or it can be a remote connection. And so, its useful to get the base
    URL for use with links on various pages.
    '''
    session_id = get_report_ctx().session_id
    session_info = Server.get_current()._get_session_info(session_id)

    if session_info:
        return f'http://{session_info.ws.request.host}/'

    return 'http://localhost:8501/'


def get_session_id():
    '''Return Streamlit's session ID'''
    return get_report_ctx().session_id


def get_main_session_by_id(session_id):
    """This returns the session state based on the ID provided

    This is relying on Streamlit internals and is not a public API.

    Args:
        session_id ([type]): The session id string

    Returns:
        [type]: session state associated with session or None
    """
    session = Server.get_current()._session_info_by_id.get(session_id, None)
    if session:
        return session.session.session_state

    return None


def get_image_dir():
    '''Get directory where images are stored'''
    return(os.path.dirname(find_spec('suzieq.gui')
                           .loader.path) + '/images')


def display_help_icon(url: str):
    '''Display Help Icon with click to take you to appropriate page'''
    help_img = f'{get_image_dir()}/helps.png'
    st.sidebar.markdown(f'<a target="_help" href="{url}"><img class="help-img" src="data:image/png;base64,{base64.b64encode(open(help_img, "rb").read()).decode()}"></a>',
                        unsafe_allow_html=True)


def maximize_browser_window():
    '''Maximize browser window in streamlit'''

    max_width_str = "max-width: 2000px;"
    st.markdown(
        f"""
    <style>
    .reportview-container .main .block-container{{
        {max_width_str}
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )


def horizontal_radio():
    '''Make the radio buttons horizontal'''
    st.write('<style>div.row-widget.stRadio > div{flex-direction:row;}</style>',
             unsafe_allow_html=True)


def hide_st_index():
    '''CSS to hide table index rendered via st.table'''
    st.markdown("""
        <style>
        .table td:nth-child(1) {
            display: none;
        }
        .table th:nth-child(1) {
            display: none;
        }
        </style>
        """, unsafe_allow_html=True)


def color_row(row, **kwargs):
    """Color the appropriate column red if the status has failed"""
    fieldval = kwargs.pop("fieldval", "down")
    field = kwargs.pop("field", "state")
    color = kwargs.pop("color", "black")
    bgcolor = kwargs.pop("bgcolor", "yellow")

    if row[field] in fieldval:
        return [f"background-color: {bgcolor}; color: {color}"]*len(row)
    else:
        return [""]*len(row)


def color_element_red(value, **kwargs):
    '''Use with applymap to color a cell based on a value'''
    fieldval = kwargs.pop("fieldval", "down")
    if value not in fieldval:
        return "background-color: red; color: white;"


def ifstate_red(row):
    '''Color interface state red if admin state is up, but not oper state'''
    llen = len(row.index.tolist())
    if row.adminState == "up" and row.state == "down":
        return ["background-color: red; color: white;"]*llen
    else:
        return ["background-color: white; color: black;"]*llen


def sq_gui_style(df, table, is_assert=False):
    """Apply appropriate styling for the dataframe based on the table"""

    if is_assert:
        if not df.empty:
            return df.style.apply(color_row, axis=1, field='status',
                                  fieldval=['fail'], bgcolor='darkred',
                                  color='white')
        else:
            return df

    if table == 'bgp' and 'state' in df.columns:
        return df.style.hide_index() \
            .applymap(color_element_red, fieldval=['Established'],
                      subset=pd.IndexSlice[:, ['state']])
    elif table == 'ospf' and 'adjState' in df.columns:
        return df.style.hide_index() \
            .applymap(color_element_red,
                      fieldval=["full", "passive"],
                      subset=pd.IndexSlice[:, ['adjState']])

    elif table == "routes" and 'prefix' in df.columns:
        return df.style.hide_index() \
            .apply(color_row, axis=1, fieldval=['0.0.0.0/0'],
                   field='prefix')
    elif table == "interfaces" and 'state' in df.columns:
        return df.style.hide_index().apply(ifstate_red, axis=1)
    elif table == "device":
        return df.style.hide_index() \
            .apply(color_row, axis=1, fieldval=['dead', 'neverpoll'],
                   field='status', bgcolor='red', color='white')
    else:
        return df.style.hide_index()


def get_color_styles(color: str) -> str:
    """Compile some hacky CSS to override the theme color."""
    # fmt: off
    color_selectors = ["a", "a:hover", "*:not(textarea).st-ex:hover", ".st-en:hover"]
    bg_selectors = [".st-da", "*:not(button).st-en:hover"]
    border_selectors = [".st-ft", ".st-fs", ".st-fr", ".st-fq", ".st-ex:hover", ".st-en:hover"]
    # fmt: on
    css_root = "#root { --primary: %s }" % color
    css_color = ", ".join(color_selectors) + "{ color: %s !important }" % color
    css_bg = ", ".join(bg_selectors) + \
        "{ background-color: %s !important }" % color
    css_border = ", ".join(border_selectors) + \
        "{ border-color: %s !important }" % color
    other = ".decoration { background: %s !important }" % color
    return f"<style>{css_root}{css_color}{css_bg}{css_border}{other}</style>"


def display_title(page: str):
    '''Render the logo and the app name'''

    state = st.session_state
    pagelist = state.pagelist
    search_text = state.search_text

    LOGO_IMAGE = f'{get_image_dir()}/logo-small.jpg'
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

    title_col, mid, page_col, srch_col = st.columns([2, 1, 2, 2])
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

    sel_pagelist = list(filter(lambda x: not x.startswith('_'), pagelist))

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
        srch_holder = st.empty()
        pageidx = sel_pagelist.index(page or 'Status')
        if 'sq_page' not in state:
            page = srch_holder.selectbox('Page', sel_pagelist, index=pageidx,
                                         key='sq_page',
                                         on_change=main_sync_state)
        else:
            page = srch_holder.selectbox('Page', sel_pagelist, key='sq_page',
                                         on_change=main_sync_state)
            page = state.sq_page

    return page, search_str


def main_sync_state():

    wsstate = st.session_state

    if wsstate.search_text != wsstate.search:
        wsstate.search_text = wsstate.search
        wsstate.page = wsstate.sq_page = 'Search'

    if wsstate.page != wsstate.sq_page:
        wsstate.page = wsstate.sq_page
        st.experimental_set_query_params(**dict())
        if wsstate.page != 'Search':
            wsstate.search_text = ''
