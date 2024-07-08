import base64
import os
from enum import Enum
from importlib.util import find_spec

import pandas as pd
import streamlit as st
from IPython.display import Markdown
from streamlit.server.server import Server
try:
    from streamlit.scriptrunner.script_run_context import get_script_run_ctx
except ModuleNotFoundError:
    # streamlit < 1.4
    from streamlit.report_thread import (  # type: ignore
        get_report_ctx as get_script_run_ctx,
    )
from suzieq.sqobjects import get_sqobject

SUZIEQ_COLOR = "#68279D"


class SuzieqMainPages(str, Enum):
    '''Pages in Suzieq GUI'''
    STATUS = "Status"
    XPLORE = "Xplore"
    PATH = "Path"
    SEARCH = "Search"


def pandas_df_to_markdown_table(df: pd.DataFrame) -> str:
    """Convert a Dataframe into a markdown table

    Args:
        df (pd.DataFrame): input dataframe

    Returns:
        str: markdown table
    """

    fmt = ['---' for i in range(len(df.columns))]
    df_fmt = pd.DataFrame([fmt], columns=df.columns)
    df_formatted = pd.concat([df_fmt, df])
    return Markdown(df_formatted.to_csv(sep="|", index=False)).data


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


@st.experimental_memo
def gui_get_df(table: str,
               config_file: str,
               verb: str = 'get', **kwargs) -> pd.DataFrame:
    """Get the cached value of the table provided

    The only verbs supported are get and find.

    Args:
        table ([str]): The table for which to get the data
        config_file ([str]): The config file for the sqobject
        verb (str, optional): . Defaults to 'get'.

    Returns:
        [pandas.DataFrame]: The dataframe

    Raises:
        ValueError: If the verb is not supported
    """
    view = kwargs.pop('view', 'latest')
    columns = kwargs.pop('columns', ['default'])
    stime = kwargs.pop('start_time', '')
    etime = kwargs.pop('end_time', '')

    sqobject = get_sqobject(table)(view=view, start_time=stime, end_time=etime,
                                   config_file=config_file)
    if columns == ['all']:
        columns = ['*']
    fn = getattr(sqobject, verb, None)
    if not fn or not callable(fn):
        raise ValueError(f'Unsupported verb {verb}')

    if verb not in ['assert', 'find']:
        df = fn(columns=columns, **kwargs)
    else:
        df = fn(**kwargs)

    if not df.empty:
        df = sqobject.humanize_fields(df)
        if table == 'address':
            if 'ipAddressList' in df.columns:
                df = df.explode('ipAddressList').fillna('')
            if 'ip6AddressList' in df.columns:
                df = df.explode('ip6AddressList').fillna('')

    if verb == 'summarize':
        return df
    if columns not in [['*'], ['default']]:
        return df[columns].reset_index(drop=True)
    return df.reset_index(drop=True)


def get_session_id():
    '''Return Streamlit's session ID'''
    ctx = get_script_run_ctx()
    if ctx is None:
        raise AttributeError("Failed to get the thread context")
    return ctx.session_id


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


def set_def_aggrid_options(grid_options: dict):
    '''Set default grid options for aggrid tables

    Invoke this function by passing it the output pf gb.build
    '''
    grid_options['rowStyle'] = {'background': 'white'}
    grid_options['cacheQuickFilter'] = True
    grid_options['suppressDragLeaveHidesColumns'] = True
    grid_options['enableCellTextSelection'] = True
    grid_options['ensureDomOrder'] = True

    return grid_options


def get_image_dir():
    '''Get directory where images are stored'''
    return (os.path.dirname(find_spec('suzieq.gui')
                            .loader.path) + '/images')


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
    # Assuming light theme here
    return "background-color: white; color: black;"


def ifstate_red(row):
    '''Color interface state red if admin state is up, but not oper state'''
    llen = len(row.index.tolist())
    if row.adminState == "up":
        if row.state == "down":
            return ["background-color: red; color: white;"]*llen
        elif row.state != "up":
            return ["color:  gray;"]*llen

    return ["background-color: white; color: black;"]*llen


def sq_gui_style(df, table, is_assert=False):
    """Apply appropriate styling for the dataframe based on the table"""

    if is_assert:
        if not df.empty:
            return df.style.apply(color_row, axis=1, field='result',
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
    color_selectors = ["a", "a:hover", "*:not(textarea).st-ex:hover",
                       ".st-en:hover"]
    bg_selectors = [".st-da", "*:not(button).st-en:hover"]
    border_selectors = [".st-ft", ".st-fs", ".st-fr", ".st-fq", ".st-ex:hover",
                        ".st-en:hover"]
    # fmt: on
    css_root = "#root { --primary: %s }" % color
    css_color = ", ".join(color_selectors) + "{ color: %s !important }" % color
    css_bg = ", ".join(bg_selectors) + \
        "{ background-color: %s !important }" % color
    css_border = ", ".join(border_selectors) + \
        "{ border-color: %s !important }" % color
    other = ".decoration { background: %s !important }" % color
    return f"<style>{css_root}{css_color}{css_bg}{css_border}{other}</style>"
