from dataclasses import dataclass
import streamlit as st

import altair as alt
from suzieq.gui.guiutils import gui_get_df
import numpy as np


def get_title():
    return 'Status'


@dataclass
class StatusSessionState:
    namespace: str = ''


def draw_sidebar_status(state, sqobjs):
    '''Draw appropriate sidebar for the page'''

    do_refresh = st.sidebar.button('Refresh')

    devdf = gui_get_df(sqobjs['device'], columns=['namespace', 'hostname'])
    if devdf.empty:
        st.error('Unable to retrieve any namespace info')
        st.stop()

    namespaces = [''] + sorted(devdf.namespace.unique().tolist())
    if state.namespace:
        nsidx = namespaces.index(state.namespace)
    else:
        nsidx = 0
    namespace = st.sidebar.selectbox('Namespace',
                                     namespaces, index=nsidx)

    if do_refresh:
        st.caching.clear_cache()

    st.sidebar.markdown(
        '''This page provides an overview of the overall network status

Select one of the following pages from the Page menu to investigate further.
* __Xplore__: Look at all the data, look at summaries, run asserts, queries and more
* __Path__: Trace the paths between destinations in a given namespace
* __Search__: Search for addresses in various tables. Just type in any address you want to search. You can specify multiple addresses, space separated. See the search page for more help.

__Caching is enabled by default for 90 secs on all pages__. You can clear the cache by hitting the refresh button on this page or selecting "Clear Cache" option from the drop down menu on the top right hand corner
''')

    if namespace != state.namespace:
        state.namespace = namespace


def page_work(state_container, page_flip: bool):
    '''The main workhorse routine for the XNA page'''

    if not state_container.statusSessionState:
        state_container.statusSessionState = StatusSessionState()

    state = state_container.statusSessionState
    draw_sidebar_status(state, state_container.sqobjs)

    col1, mid, col2 = st.beta_columns([2, 1, 2])
    with col1:
        dev_gr = st.empty()
    with col2:
        if_gr = st.empty()
    col3, mid, col4 = st.beta_columns([2, 1, 2])
    with col3:
        bgp_gr = st.empty()
    with col4:
        ospf_gr = st.empty()

    # Get each of the summarize info
    if state.namespace:
        ns = [state.namespace]
    else:
        ns = []
    dev_df = gui_get_df(state_container.sqobjs['device'], namespace=ns,
                        columns=['*'])
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
        dev_gr.altair_chart(dev_chart)
    else:
        dev_gr.info('No device info found')

    if_df = gui_get_df(state_container.sqobjs['interfaces'],
                       namespace=ns, columns=['*'])
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
        if_gr.altair_chart(if_chart)
    else:
        if_gr.info('No Interface info found')

    bgp_df = gui_get_df(state_container.sqobjs['bgp'], namespace=ns,
                        columns=['*'])

    if not bgp_df.empty and ('error' not in bgp_df):
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
        bgp_gr.altair_chart(bgp_chart)

    ospf_df = gui_get_df(state_container.sqobjs['ospf'],
                         namespace=ns, columns=['*'])
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
        ospf_gr.altair_chart(ospf_chart)

    sqdf = gui_get_df(state_container.sqobjs['sqPoller'],
                      columns=['namespace', 'hostname', 'timestamp'],
                      service='device', namespace=ns)
    if not sqdf.empty:
        hosts = sqdf.groupby(by=['namespace'])['hostname'] \
                    .nunique() \
                    .reset_index() \
                    .rename({'hostname': '#devices'}, axis=1)
        times = sqdf.groupby(by=['namespace'])['timestamp'] \
                    .max().reset_index() \
                          .rename({'timestamp': 'lastPolledTime'}, axis=1)
        pstats = times.merge(hosts, on=['namespace'])

        st.subheader('Poller Status')
        st.dataframe(pstats)

    st.experimental_set_query_params(**{})
