from dataclasses import dataclass
from importlib.util import find_spec
import os
from pathlib import Path

import streamlit as st


@dataclass
class HelpSessionState:
    help_on: str = ''


def get_title():
    # suzieq_gui.py has hardcoded this name.
    return '_Help_'


def help_sidebar(state: HelpSessionState, helpdir: str):
    '''Sidebar page for help'''

    filelist = Path(helpdir).glob('*.md')
    help_pages = [x.name[:-3] for x in filelist]
    help_on = st.sidebar.selectbox(label='Help On...', options=help_pages)

    return help_on


def page_work(state_container, page_flip: bool):
    '''Main page workhorse'''

    if not state_container.helpSessionState:
        state_container.helpSessionState = HelpSessionState()

    state = state_container.helpSessionState

    url_params = st.experimental_get_query_params()
    help_on = url_params.get('help_on', [''])[0]

    if not help_on:
        st.info('Nothing to show help about')
        st.stop()

    helpdir = os.path.dirname(
        find_spec('suzieq.gui.pages').loader.path) + '/help'

    page_help_on = help_sidebar(state, helpdir)

    helptext = ''
    with open(f'{helpdir}/{help_on}.md', 'r') as f:
        helptext = f.read()

    if helptext:
        st.markdown(helptext)

    st.experimental_set_query_params(
        **{'page': '_Help_', 'help_on': help_on})
