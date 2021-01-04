from importlib.util import find_spec
import os
import base64

import streamlit as st
import pandas as pd
from streamlit.server.server import Server
from streamlit.report_thread import get_report_ctx


@st.cache(ttl=90, allow_output_mutation=True, show_spinner=False,
          max_entries=20)
def gui_get_df(sqobject, **kwargs):
    table = kwargs.pop('_table', '')
    view = kwargs.pop('view', 'latest')
    columns = kwargs.pop('columns', ['default'])
    stime = kwargs.pop('start_time', '')
    etime = kwargs.pop('end_time', '')
    if columns == ['all']:
        columns = ['*']
    if table != "tables":
        df = sqobject(view=view, start_time=stime, end_time=etime) \
            .get(columns=columns, **kwargs)
    else:
        df = sqobject(view=view, start_time=stime, end_time=etime) \
            .get(**kwargs)
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
    if row[field] == fieldval:
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
                                  fieldval='fail', bgcolor='darkred',
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
            .apply(color_row, axis=1, fieldval='0.0.0.0/0',
                   field='prefix')
    elif table == "interfaces" and 'state' in df.columns:
        return df.style.hide_index().apply(ifstate_red, axis=1)
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
