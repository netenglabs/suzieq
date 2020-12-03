import streamlit as st
from suzieq.sqobjects.path import PathObj
import graphviz as graphviz
import suzieq.gui.SessionState as SessionState
from PIL import Image
from suzieq.sqobjects import *
from suzieq.gui.guiutils import horizontal_radio, display_title, hide_st_index


@st.cache
def get_path(namespace, source, dest, vrf):
    '''Run the path and return the dataframes'''
    df = PathObj().get(namespace=[namespace],
                       source=source, dest=dest, vrf=vrf)
    summ_df = PathObj().summarize(namespace=[namespace],
                                  source=source, dest=dest,
                                  vrf=vrf)
    return df, summ_df


def sidebar():
    """Configure sidebar"""

    ok_button = st.sidebar.button('Trace')
    namespace = st.sidebar.text_input('Namespace', key='namespace')
    source = st.sidebar.text_input('Source IP', key='source')
    dest = st.sidebar.text_input('Dest IP', key='dest')
    vrf = st.sidebar.text_input('VRF', key='vrf')

    return (ok_button, namespace, source, dest, vrf)


@st.cache
def get_logo():
    """Get Suzieq Logo"""
    image = Image.open('/home/ddutt/Pictures/logo-small.png')
    return image


def _main():

    # Retrieve data from prev session state
    state = SessionState.get(vrf='', namespace='',
                             source='', dest='', run=False)

    st.set_page_config(layout="wide")
    hide_st_index()
    display_title()
    horizontal_radio()
    run, namespace, source, dest, vrf = sidebar()

    if run:
        state.run = True
        state.namespace = namespace
        state.source = source
        state.dest = dest
        state.vrf = vrf

    if state.run:
        df, summ_df = get_path(state.namespace, state.source, state.dest,
                               state.vrf)

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


if __name__ == "__main__":
    _main()
