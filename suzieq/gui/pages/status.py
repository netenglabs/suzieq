import streamlit as st
import suzieq.gui.SessionState as SessionState
import altair as alt
import pandas as pd
from dataclasses import dataclass

from suzieq.sqobjects import *


@dataclass
class StatusSessionState:
    add_vlans: bool = False
    add_vrfs: bool = False
    add_macs: bool = False
    add_routes: bool = False


def get_title():
    return 'Status'


def draw_sidebar_status(state: SessionState):
    '''Draw appropriate sidebar for the page'''

    state.add_vlans = st.sidebar.checkbox('Add VLAN Count',
                                          value=state.add_vlans)
    state.add_vrfs = st.sidebar.checkbox('Add VRF Count',
                                         value=state.add_vrfs)
    state.add_macs = st.sidebar.checkbox('Add MACs Count',
                                         value=state.add_macs)
    state.add_routes = st.sidebar.checkbox('Add Routes Count',
                                           value=state.add_routes)


def init_state(state_container: SessionState) -> StatusSessionState:

    state_container.statusSessionState = state = StatusSessionState()

    return state


def page_work(state_container: SessionState, page_flip: bool = False):
    '''The main workhorse routine for the XNA page'''

    if hasattr(state_container, 'statusSessionState'):
        state = getattr(state_container, 'statusSessionState')
    else:
        state = init_state(state_container)

    draw_sidebar_status(state)
