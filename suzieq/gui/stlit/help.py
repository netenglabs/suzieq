from dataclasses import dataclass
from pathlib import Path
from importlib.util import find_spec

import streamlit as st

from suzieq.gui.stlit.pagecls import SqGuiPage


@dataclass
class HelpSessionState:
    '''Session state for status page'''
    page: str = 'Help'
    help_on: str = ''


class HelpPage(SqGuiPage):
    '''Page for Path trace page'''
    _title: str = 'Help'
    _state: HelpSessionState = HelpSessionState()
    _helpdir: Path = Path(
        find_spec('suzieq.gui').loader.path).parent / 'help-pages'

    @property
    def add_to_menu(self) -> bool:
        return False

    def build(self):
        self._get_state_from_url()
        self._create_sidebar()
        self._render(None)

    def _create_sidebar(self) -> None:

        filelist = Path(self._helpdir).glob('*.md')
        help_pages = [x.name[:-3] for x in filelist]
        help_on = st.sidebar.selectbox(label='Help On...', options=help_pages)

        return help_on

    def _create_layout(self) -> None:
        pass

    def _render(self, layout: dict) -> None:
        if not self._state.help_on:
            st.info('Nothing to show help about')
            st.stop()

        helptext = ''
        helpfile = self._helpdir / f'{self._state.help_on}.md'
        with open(helpfile, 'r') as f:
            helptext = f.read()

        if helptext:
            st.markdown(helptext)

    def _sync_state(self) -> None:
        pass
