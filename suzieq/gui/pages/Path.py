import streamlit as st
from suzieq.sqobjects.path import PathObj
import graphviz as graphviz
import suzieq.gui.SessionState as SessionState


def get_title():
    return 'Path'


@st.cache(ttl=90, allow_output_mutation=True, suppress_st_warning=True)
def path_get(namespace, source, dest, vrf):
    '''Run the path and return the dataframes'''
    try:
        df = PathObj().get(namespace=[namespace],
                           source=source, dest=dest, vrf=vrf)
        summ_df = PathObj().summarize(namespace=[namespace],
                                      source=source, dest=dest,
                                      vrf=vrf)
    except Exception as e:
        st.error(f'Invalid Input: {str(e)}')
        st.stop()
    return df, summ_df


def path_sidebar(state, page_flip: bool):
    """Configure sidebar"""

    ok_button = st.sidebar.button('Trace')
    val = state.path_namespace if page_flip else ''
    state.path_namespace = st.sidebar.text_input('Namespace',
                                                 value=val,
                                                 key='namespace')
    state.path_source = st.sidebar.text_input('Source IP',
                                              value=state.path_source,
                                              key='source')
    state.path_dest = st.sidebar.text_input('Dest IP', value=state.path_dest,
                                            key='dest')
    state.path_vrf = st.sidebar.text_input('VRF', value=state.path_vrf,
                                           key='vrf')

    if all(not x for x in [state.path_namespace,
                           state.path_source,
                           state.path_dest]):
        state.path_run = False
    elif ok_button:
        state.path_run = True

    return


def path_run(state: SessionState, page_flip: bool = False):
    '''Main workhorse routine for path'''

    path_sidebar(state, page_flip)

    if state.path_run:
        df, summ_df = path_get(state.path_namespace, state.path_source,
                               state.path_dest, state.path_vrf)

    if not state.path_run:
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
