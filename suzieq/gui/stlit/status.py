from dataclasses import dataclass
from typing import List

import numpy as np
import streamlit as st
import altair as alt

from suzieq.gui.stlit.guiutils import gui_get_df, SuzieqMainPages
from suzieq.gui.stlit.pagecls import SqGuiPage


@dataclass
class StatusSessionState:
    '''Session state for status page'''
    page: str = SuzieqMainPages.STATUS.value
    namespace: str = ''


class StatusPage(SqGuiPage):
    '''Page for Main status page'''
    _title: str = SuzieqMainPages.STATUS.value
    _state: StatusSessionState = StatusSessionState()
    _config_file: str = st.session_state.get('config_file', '')

    @property
    def add_to_menu(self):
        return True

    def build(self):
        self._get_state_from_url()
        self._create_sidebar()
        layout = self._create_layout()
        self._render(layout)

    def _create_sidebar(self) -> None:
        '''Draw appropriate sidebar for the page'''

        do_refresh = st.sidebar.button('Refresh')

        devdf = gui_get_df('device', self._config_file,
                           columns=['namespace', 'hostname'])
        if devdf.empty:
            st.error('Unable to retrieve any namespace info')
            st.stop()

        namespaces = [''] + sorted(devdf.namespace.unique().tolist())

        nsidx = 0
        if self._state.namespace and self._state.namespace in namespaces:
            nsidx = namespaces.index(self._state.namespace)
        namespace = st.sidebar.selectbox('Namespace', namespaces, index=nsidx,
                                         key='status_ns',
                                         on_change=self._sync_state)

        if do_refresh:
            st.experimental_memo.clear()

        st.sidebar.markdown(
            '''This page provides an overview of the overall network status

Select one of the following pages from the Page menu to investigate further.
* __Xplore__: Look at all the data, look at summaries, run asserts, queries
              and more
* __Path__: Trace the paths between destinations in a given namespace
* __Search__: Search for addresses in various tables. Just type in any address
              you want to search. You can specify multiple addresses, space
               separated. See the search page for more help.

__Caching is enabled by default for 90 secs on all pages__. You can clear the
 cache by hitting the refresh button on this page or selecting "Clear Cache"
 option from the drop down menu on the top right hand corner
        ''')

        if namespace != self._state.namespace:
            self._state.namespace = namespace

    def _create_layout(self) -> dict:
        col1, _, col2 = st.columns([2, 1, 2])
        with col1:
            dev_chart = st.empty()
        with col2:
            if_chart = st.empty()
        col3, _, col4 = st.columns([2, 1, 2])
        with col3:
            bgp_chart = st.empty()
        with col4:
            ospf_chart = st.empty()

        poller_ph = st.empty()

        return {
            'dev_chart': dev_chart,
            'if_chart': if_chart,
            'ospf_chart': ospf_chart,
            'bgp_chart': bgp_chart,
            'poller': poller_ph,
        }

    def _render(self, layout) -> None:
        '''Render the page'''
        if self._state.namespace:
            ns_list = [self._state.namespace]
        else:
            ns_list = []

        self._chart_dev(layout, ns_list)
        self._chart_interface(layout, ns_list)
        self._chart_bgp(layout, ns_list)
        self._chart_ospf(layout, ns_list)
        self._chart_poller(layout, ns_list)

    def _sync_state(self) -> None:
        wsstate = st.session_state

        self._state.namespace = wsstate.status_ns
        self._save_page_url()

    def _chart_dev(self, layout: dict, ns_list: List[str]) -> None:
        '''Chart the devices table status'''

        dev_df = gui_get_df('device', self._config_file,
                            namespace=ns_list, columns=['*'])
        if dev_df.empty:
            layout['dev_chart'].warning('No device info found')
            return

        dev_status = dev_df \
            .groupby(by=['namespace', 'status'])['hostname'].count() \
            .reset_index() \
            .rename({'hostname': 'count'}, axis=1)

        dev_chart = alt.Chart(dev_status, title='Devices') \
                       .mark_bar(tooltip=True) \
                       .encode(y='status', x='count:Q', row='namespace',
                               color=alt.Color(
                                   'status',
                                   scale=alt.Scale(
                                       domain=[
                                           'alive', 'dead', 'neverpoll'],
                                       range=['green', 'red', 'darkred']))
                               )
        layout['dev_chart'].altair_chart(dev_chart)

    def _chart_interface(self, layout: dict, ns_list: List[str]) -> None:
        '''Chart the interfaces table status'''

        if_df = gui_get_df('interfaces', self._config_file,
                           namespace=ns_list,
                           columns=['default'])
        if if_df.empty:
            layout['if_chart'].warning('No Interface info found')
            return

        if_df['state'] = np.where((if_df.state == "down") & (
            if_df.adminState == "down"), "adminDown", if_df.state)

        if_status = if_df.groupby(by=['namespace', 'state'])['hostname'] \
                         .count() \
                         .reset_index() \
                         .rename({'hostname': 'count'}, axis=1)

        if_chart = alt \
            .Chart(if_status, title='Interfaces') \
            .mark_bar(tooltip=True) \
            .encode(y='state', x='count:Q', row='namespace',
                    color=alt.Color(
                        'state',
                        scale=alt.Scale(domain=['up', 'errDisabled',
                                                'down', 'notPresent',
                                                'notConnected'],
                                        range=['green', 'darkred',
                                               'red', 'grey', 'darkgray']))
                    )
        layout['if_chart'].altair_chart(if_chart)

    def _chart_bgp(self, layout: dict, ns_list: List[str]) -> None:
        '''Chart the BGP table status'''

        bgp_df = gui_get_df('bgp', self._config_file,
                            namespace=ns_list, columns=['default'])

        if bgp_df.empty:
            return

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
        layout['bgp_chart'].altair_chart(bgp_chart)

    def _chart_ospf(self, layout: dict, ns_list: List[str]) -> None:
        '''Chart OSPF status'''

        ospf_df = gui_get_df('ospf', self._config_file,
                             namespace=ns_list, columns=['default'])
        if ospf_df.empty:
            return

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
                                        range=['green', 'red', 'orange',
                                               'peach']))
                                )
        layout['ospf_chart'].altair_chart(ospf_chart)

    def _chart_poller(self, layout: dict, ns_list: List[str]) -> None:
        '''Display poller status'''

        sqdf = gui_get_df('sqPoller',
                          self._config_file,
                          columns=['namespace', 'hostname', 'timestamp'],
                          service='device', namespace=ns_list)
        if sqdf.empty:
            st.warning('No Poller information found')
            return

        hosts = sqdf.groupby(by=['namespace'])['hostname'] \
                    .nunique() \
                    .reset_index() \
                    .rename({'hostname': '#devices'}, axis=1)
        times = sqdf.groupby(by=['namespace'])['timestamp'] \
                    .max().reset_index() \
                          .rename({'timestamp': 'lastPolledTime'}, axis=1)
        pstats = times.merge(hosts, on=['namespace'])

        layout['poller'].subheader('Poller Status')
        layout['poller'].dataframe(pstats)
