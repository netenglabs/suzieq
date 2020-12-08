from dataclasses import dataclass

import streamlit as st
import pandas as pd
from suzieq.sqobjects.path import PathObj
import graphviz as graphviz


@dataclass
class PathSessionState:
    run: bool = False
    namespace: str = ''
    source: str = ''
    dest: str = ''
    start_time: str = ''
    end_time: str = ''
    vrf: str = ''


def get_title():
    return 'Path'


@st.cache(ttl=90, allow_output_mutation=True, suppress_st_warning=True)
def path_get(state: PathSessionState) -> (pd.DataFrame, pd.DataFrame):
    '''Run the path and return the dataframes'''
    try:
        df = PathObj(start_time=state.start_time, end_time=state.end_time) \
            .get(namespace=[state.namespace],
                 source=state.source, dest=state.dest, vrf=state.vrf)

        summ_df = PathObj(start_time=state.start_time,
                          end_time=state.end_time) \
            .summarize(namespace=[state.namespace],
                       source=state.source, dest=state.dest,
                       vrf=state.vrf)
    except Exception as e:
        st.error(f'Invalid Input: {str(e)}')
        st.stop()
    return df, summ_df


def path_sidebar(state):
    """Configure sidebar"""

    ok_button = st.sidebar.button('Trace')
    state.namespace = st.sidebar.text_input('Namespace',
                                            value=state.namespace,
                                            key='namespace')
    state.source = st.sidebar.text_input('Source IP',
                                         value=state.source,
                                         key='source')
    state.dest = st.sidebar.text_input('Dest IP', value=state.dest,
                                       key='dest')
    state.vrf = st.sidebar.text_input('VRF', value=state.vrf,
                                      key='vrf')
    state.start_time = st.sidebar.text_input('Start Time',
                                             value=state.start_time,
                                             key='start-time')
    state.end_time = st.sidebar.text_input('End Time',
                                           value=state.end_time,
                                           key='end-time')

    if all(not x for x in [state.namespace,
                           state.source,
                           state.dest]):
        state.run = False
    elif ok_button:
        state.run = True

    return


def page_work(state_container, page_flip: bool):
    '''Main workhorse routine for path'''

    if not state_container.pathSessionState:
        state_container.pathSessionState = PathSessionState()

    state = state_container.pathSessionState

    path_sidebar(state)

    if state.run:
        df, summ_df = path_get(state)

    if not state.run:
        st.stop()

    g = graphviz.Digraph()

    for hostname in df.hostname.unique().tolist():
        if hostname:
            g.node(hostname, style='filled')

    df['prevhop'] = df.hostname.shift(1)
    df.prevhop = df.prevhop.fillna('')
    pathid = 0
    prevhop = None
    connected_set = set()
    for row in df.itertuples():
        if row.pathid != pathid:
            prevhop = row.hostname
            pathid = row.pathid
            oif = row.oif
            continue
        if row.prevhop:
            conn = (prevhop, row.hostname)
            if conn not in connected_set:
                if row.overlay:
                    color = 'green'
                else:
                    color = 'black'
                g.edge(prevhop, row.hostname, dir='none', color=color)
                connected_set.add(conn)
            prevhop = row.hostname
            oif = row.oif

    if not df.empty:
        summary = st.beta_container()
        summcol, pathcol = summary.beta_columns([1, 1])
        with summary:
            with summcol:
                st.dataframe(data=summ_df)
            with pathcol:
                st.graphviz_chart(g)

        table_expander = st.beta_expander('Path Table', expanded=True)
        with table_expander:
            df.drop(columns=['prevhop'], inplace=True)
            st.dataframe(data=df)
