import streamlit as st
import suzieq.gui.SessionState as SessionState
import altair as alt
import pandas as pd

from suzieq.sqobjects import *


def draw_sidebar_overview(state: SessionState):
    '''Draw appropriate sidebar for the page'''

    state.overview_add_vlans = st.sidebar.checkbox('Add VLAN Count',
                                                   value=state.overview_add_vlans)
    state.overview_add_vrfs = st.sidebar.checkbox('Add VRF Count',
                                                  value=state.overview_add_vrfs)
    state.overview_add_macs = st.sidebar.checkbox('Add MACs Count',
                                                  value=state.overview_add_macs)
    state.overview_add_routes = st.sidebar.checkbox('Add Routes Count',
                                                    value=state.overview_add_routes)


def overview_run(state: SessionState, page_flip: bool = False):
    '''The main workhorse routine for the XNA page'''

    draw_sidebar_overview(state)
