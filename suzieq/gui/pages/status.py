import streamlit as st
import suzieq.gui.SessionState as SessionState
import pandas as pd
import altair as alt
from dataclasses import dataclass
from suzieq.gui.guiutils import gui_get_df
import numpy as np


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

    st.sidebar.markdown(
        '''This page provides an overview of the overall network status

Select one of the following pages from the Page menu to investigate further.
* __Xplore__: Look at all the data, look at summaries, run asserts, queries and more
* __Path__: Trace the paths between destinations in a given namespace
* __Search__: Search for addresses in various tables. You can search for more things in the upcoming releases
''')


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

    container_1 = st.beta_container()
    col1, mid, col2 = st.beta_columns([2, 1, 2])

    # Get each of the summarize info
    dev_df = gui_get_df(state_container.sqobjs['device'], columns=['*'])
    if not dev_df.empty:
        dev_status = dev_df.groupby(by=['namespace', 'status'])['hostname'] \
                           .count() \
                           .reset_index() \
                           .rename({'hostname': 'count'}, axis=1)

        dev_chart = alt.Chart(dev_status, title='Devices') \
                       .mark_bar(tooltip=True) \
                       .encode(y='status', x='count:Q', row='namespace',
                               color=alt.Color(
                                   'status',
                                   scale=alt.Scale(domain=['alive', 'dead'],
                                                   range=['green', 'red']))
                               )
        with container_1:
            with col1:
                st.altair_chart(dev_chart)
    else:
        with container_1:
            with col1:
                st.info('No device info found')

    if_df = gui_get_df(state_container.sqobjs['interfaces'], columns=['*'])
    if not if_df.empty:
        if_df['state'] = np.where((if_df.state == "down") & (
            if_df.adminState == "down"), "adminDown", if_df.state)

        if_status = if_df.groupby(by=['namespace', 'state'])['hostname'] \
                         .count() \
                         .reset_index() \
                         .rename({'hostname': 'count'}, axis=1)

        if_chart = alt.Chart(if_status, title='Interfaces') \
                      .mark_bar(tooltip=True) \
                      .encode(y='state', x='count:Q', row='namespace',
                              color=alt.Color(
                                  'state',
                                  scale=alt.Scale(domain=['up', 'adminDown',
                                                          'down'],
                                                  range=['green', 'orange',
                                                         'red']))
                              )
        with container_1:
            with col2:
                st.altair_chart(if_chart)
    else:
        with container_1:
            with col2:
                st.info('No Interface info found')

    bgp_df = gui_get_df(state_container.sqobjs['bgp'], columns=['*'])

    if not bgp_df.empty:
        bgp_status = bgp_df.groupby(by=['namespace', 'state'])['hostname'] \
                           .count() \
                           .reset_index() \
                           .rename({'hostname': 'count'}, axis=1)

        bgp_chart = alt.Chart(bgp_status, title='BGP') \
                       .mark_bar(tooltip=True) \
                       .encode(y='state', x='count:Q', row='namespace',
                               color=alt.Color(
                                   'state',
                                   scale=alt.Scale(
                                       domain=['Established',
                                               'NotEstd', 'dynamic'],
                                       range=['green', 'red', 'orange']))
                               )

    ospf_df = gui_get_df(state_container.sqobjs['ospf'], columns=['*'])
    if not ospf_df.empty:
        ospf_df['state'] = np.where(ospf_df.ifState == "adminDown",
                                    "adminDown", ospf_df.adjState)

        ospf_status = ospf_df.groupby(by=['namespace', 'state'])['hostname'] \
                             .count() \
                             .reset_index() \
                             .rename({'hostname': 'count'}, axis=1)

        ospf_chart = alt.Chart(ospf_status, title='OSPF') \
                        .mark_bar(tooltip=True) \
                        .encode(y='state', x='count:Q', row='namespace',
                                color=alt.Color(
                                    'state',
                                    scale=alt.Scale(
                                        domain=['full', 'fail',
                                                'adminDown', 'passive'],
                                        range=['green', 'red', 'orange', 'peach']))
                                )

    container_2 = st.beta_container()
    col2_1, mid, col2_2 = st.beta_columns([2, 1, 2])
    with container_2:
        with col2_1:
            if not bgp_df.empty:
                st.altair_chart(bgp_chart)
        with col2_2:
            if not ospf_df.empty:
                st.altair_chart(ospf_chart)
