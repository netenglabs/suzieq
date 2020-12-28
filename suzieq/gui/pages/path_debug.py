from collections import deque
from dataclasses import dataclass, asdict

import pandas as pd
import streamlit as st
from suzieq.gui.guiutils import gui_get_df


def get_title():
    # suzieq_gui.py has hardcoded this name.
    return '_Path_Debug_'


def path_debug_sidebar(state):
    '''Draw the sidebar'''

    st.sidebar.markdown(
        """Displays information from the various tables used to build path""")


def handle_edge_url(url_params: dict, pathSession):
    '''Display tables associated with a link'''

    namespace = url_params.get('namespace', [""])[0]
    hostname = url_params.get('hostname', [""])[0]
    nhip = url_params.get('nhip', [""])[0]
    vrf = url_params.get('vrf', [""])[0]
    ifhost = url_params.get('ifhost', [""])[0]
    macaddr = url_params.get('macaddr', [""])[0]
    if nhip == '169.254.0.1':
        # 169.254.0.1 is a dummy interface IP used by Cumulus
        nhip = ''

    if not hostname:
        st.error('No hostname found to display information for')
        st.stop()

    st.header(f'Debug Tables for Path from {pathSession.source} to '
              f'{pathSession.dest}')
    st.subheader(f'Hop between {hostname} and {ifhost}')

    pathobj = getattr(pathSession, 'pathobj', None)

    if not macaddr:
        with st.beta_expander(f'Route Table for {hostname}', expanded=True):
            st.dataframe(data=pathobj.engine_obj._rdf.query(
                f'hostname=="{hostname}" and vrf=="{vrf}"'))

        if nhip:
            with st.beta_expander(f'ARP/ND Table for {hostname}',
                                  expanded=True):
                st.dataframe(data=pathobj.engine_obj._arpnd_df.query(
                    f'hostname=="{hostname}" and ipAddress=="{nhip}"'))

            with st.beta_expander('Interface Table for matching next hop '
                                  f'{nhip}', expanded=True):
                if_df = pathobj.engine_obj._if_df
                s = if_df.ipAddressList.explode().str.startswith(f'{nhip}/') \
                                                     .dropna()
                s = s.loc[s == True]
                st.dataframe(data=pathobj.engine_obj._if_df
                             .iloc[s.loc[s == True].index])
    else:
        with st.beta_expander(f'MAC Table for {hostname}, MAC addr {macaddr}',
                              expanded=True):
            st.dataframe(data=pathobj.engine_obj._macsobj.get(
                namespace=namespace, hostname=hostname, macaddr=macaddr))


def handle_hop_url(url_params, pathSession):
    '''Handle table display associated with hop'''

    namespace = url_params.get('namespace', [""])[0]
    hostname = url_params.get('hostname', [""])[0]

    if not hostname:
        st.error('No hostname found to display information for')
        st.stop()

    st.header(f'Debug Tables for Path from {pathSession.source} to '
              f'{pathSession.dest}')
    st.subheader(f'Lookups on {hostname}')

    pathobj = getattr(pathSession, 'pathobj', None)
    df = getattr(pathSession, 'path_df', None)

    if df.empty:
        st.warning('Empty path dataframe')
        st.stop()

    host_dfg = df.query(f'hostname == "{hostname}"') \
                 .groupby(by=['hopCount'])

    df2 = host_dfg.agg({'vrf': ['first'], 'nexthopIp': ['first'],
                        'macLookup': ['first'],
                        'vtepLookup': ['first']}).reset_index()
    df2.columns = ['hopCount', 'vrf', 'nexthopIp', 'macaddr', 'vtepLookup']
    df2.drop_duplicates(subset=['vrf', 'nexthopIp', 'macaddr', 'vtepLookup'],
                        inplace=True)
    for row in df2.itertuples():
        if row.macaddr:
            with st.beta_expander(f'MAC Table on {hostname}, MAC addr '
                                  f'{row.macaddr}', expanded=True):
                st.dataframe(data=pathobj.engine_obj._macsobj.get(
                    namespace=namespace, hostname=hostname, macaddr=macaddr))
            continue

        with st.beta_expander(f'Route Lookup on {hostname}', expanded=True):
            st.dataframe(data=pathobj.engine_obj._rdf.query(
                f'hostname=="{hostname}" and vrf=="{row.vrf}"'))
        with st.beta_expander(f'ARPND Lookup on {hostname} for {row.nexthopIp}',
                              expanded=True):
            st.dataframe(data=pathobj.engine_obj._arpnd_df.query(
                f'hostname=="{hostname}" and ipAddress=="{row.nexthopIp}"'))


def page_work(state_container, page_flip: bool):
    '''Main page workhorse'''

    pathSession = state_container.pathSessionState

    if pathSession:
        pathobj = getattr(pathSession, 'pathobj', None)
    else:
        st.error('No saved path session found.')
        st.stop()

    if not pathobj:
        st.error('No saved path object found.')
        st.stop()

    path_debug_sidebar(pathSession)

    url_params = st.experimental_get_query_params()
    if url_params.get('lookupType', 'hop') == ['hop']:
        handle_hop_url(url_params, pathSession)
    else:
        handle_edge_url(url_params, pathSession)
