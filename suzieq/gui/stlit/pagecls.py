'''
SuzieQ Page interface.
Any page built inside the SuzieQ GUI has to adhere to this interface
'''
from abc import ABC, abstractmethod
from dataclasses import asdict

import streamlit as st
from suzieq.shared.sq_plugin import SqPlugin


class SqGuiPage(ABC, SqPlugin):
    '''A SuzieQ GUI Page Interface class
    Every page has access to the config and context via the state variable
    passed in building the page
    '''

    _state = {}  # Set it to a dataclass specific to the page
    _title: str = None  # Initialized by each page
    _first_time: bool = True
    _URL_PARAMS_BLACKLIST = ['get_clicked', 'uniq_clicked', 'tables_obj']
    _LIST_URL_PARAMS = ['columns']

    @property
    @abstractmethod
    def add_to_menu(self) -> bool:
        '''Should this page be added to the menu?'''
        return NotImplementedError

    @property
    def title(self) -> str:
        '''Page title

        Mandatory function if you want to display a page
        '''
        return self._title

    @abstractmethod
    def build(self) -> None:
        '''The main page building routine'''
        # The basic template is:
        # 1. Create sidebar (all user input is provided via sidebar)
        # 2. Create layout
        # 3. Perform appropriate computations
        # 4. Display the info using the layout
        # 5. Sync widget state if necessary (status page does nothing for this)
        # 6. Save params as a URL to share page with others
        raise NotImplementedError

    def _get_state_from_url(self):
        url_params = st.experimental_get_query_params()
        page = url_params.pop('page', '')

        if self._title in page:

            if url_params and not all(not x for x in url_params.values()):
                for key, val in url_params.items():
                    # Do not add the params that are in the blacklist
                    if key in self._URL_PARAMS_BLACKLIST:
                        continue
                    if (isinstance(val, list) and
                            key not in self._LIST_URL_PARAMS):
                        val = val[0].strip()
                    if not val:
                        continue
                    if hasattr(self._state, key):
                        if isinstance(getattr(self._state, key), bool):
                            val = val == 'True'
                        setattr(self._state, key, val)

    @abstractmethod
    def _create_sidebar(self) -> None:
        '''Draw the sidebar for this page'''
        raise NotImplementedError

    @abstractmethod
    def _create_layout(self) -> None:
        '''Create the page layout

        By creating a layout first, you avoid screen flicker and such
        when rendering the page first and then loading the data. This
        is specifically the case with pages like Xplore.
        '''
        raise NotImplementedError

    @abstractmethod
    def _render(self, layout: dict) -> None:
        '''Render the page with all the computations'''
        raise NotImplementedError

    @abstractmethod
    def _sync_state(self) -> None:
        '''Save the widget states'''
        raise NotImplementedError

    def _save_page_url(self) -> None:
        '''Save the page params as an URL for sharing'''
        state = asdict(self._state)
        for param in self._URL_PARAMS_BLACKLIST:
            state.pop(param, None)
        st.experimental_set_query_params(**state)
