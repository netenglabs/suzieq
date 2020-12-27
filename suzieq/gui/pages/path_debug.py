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


def page_work(state_container, page_flip: bool):
    '''Main page workhorse'''

    pathSession = state_container.pathSessionState
    if pathSession:
        pathobj = getattr(pathSession, 'pathobj', None)
    else:
        st.error('No saved path session found.')
        st.stop()

    url_params = st.experimental_get_query_params()
    hostname = url_params.get('hostname', '')[0]
    ifhost = url_params.get('ifhost', '')[0]
    nhip = url_params.get('nhip', '')[0]
    iif = url_params.get('iif', '')[0]
    macaddr = url_params.get('macaddr', '')[0]
    if nhip == '169.254.0.1':
        # 169.254.0.1 is a dummy interface IP used by Cumulus
        nhip = ''

    path_debug_sidebar(pathSession)
    if not pathobj:
        st.error('No saved path object found.')
        st.stop()
    if not hostname:
        st.error('No hostname found to display information for')
        st.stop()

    st.header(f'Debug Tables for Path from {pathSession.source} to '
              f'{pathSession.dest}')

    with st.beta_expander(f'Route Table for {hostname}', expanded=True):
        st.dataframe(data=pathobj.engine_obj._rdf.query(
            f'hostname=="{hostname}"'))

    with st.beta_expander(f'ARP/ND Table for {hostname}', expanded=True):
        st.dataframe(data=pathobj.engine_obj._arpnd_df.query(
            f'hostname=="{hostname}" and ipAddress=="{nhip}"'))

    if nhip:
        with st.beta_expander(f'Interface Table for matching next hop {nhip}',
                              expanded=True):
            if_df = pathobj.engine_obj._if_df.query(f'hostname=="{ifhost}"')
            s = if_df.ipAddressList.explode().str.startswith(f'{nhip}/') \
                                                 .dropna().drop_duplicates()
            s = s.loc[s == True]
            st.dataframe(data=pathobj.engine_obj._if_df
                         .iloc[s.loc[s == True].index])
