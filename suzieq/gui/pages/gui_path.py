from dataclasses import dataclass, asdict, fields, field

import streamlit as st
import pandas as pd
import graphviz as graphviz
from urllib.parse import quote

from suzieq.sqobjects.path import PathObj
from suzieq.utils import humanize_timestamp
from suzieq.gui.guiutils import gui_get_df


def get_title():
    return 'Path'


def make_fields_failed_df():
    '''return a dictionary as this is the only way dataclassses work'''

    return [{'name': 'interfaces', 'df': pd.DataFrame(), 'state': 'down'},
            {'name': 'mlag', 'df': pd.DataFrame()},
            {'name': 'ospf', 'df': pd.DataFrame(), 'state': 'other'},
            {'name': 'bgp', 'df': pd.DataFrame(), 'state': 'NotEstd'}]


@dataclass
class PathSessionState:
    run: bool = False
    namespace: str = ''
    source: str = ''
    dest: str = ''
    start_time: str = ''
    end_time: str = ''
    show_ifnames: bool = False
    vrf: str = ''


@dataclass
class FailedDFs:
    dfs: list = field(default_factory=make_fields_failed_df)


@st.cache(ttl=120, allow_output_mutation=True)
def path_get(state: PathSessionState, forward_dir: bool) -> (pd.DataFrame,
                                                             pd.DataFrame):
    '''Run the path and return the dataframes'''
    try:
        if forward_dir:
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


def get_failed_data(state: PathSessionState, pgbar, path_df,
                    sqobjs) -> FailedDFs:
    '''Get interface/mlag/routing protocol states that are failed'''

    hostlist = path_df.hostname.unique().tolist()
    faileddfs = FailedDFs()

    progress = 40
    for i, entry in enumerate(faileddfs.dfs):
        if 'state' in entry:
            entry['df'] = gui_get_df(sqobjs[entry['name']],
                                     namespace=[state.namespace],
                                     hostname=hostlist, state=entry['state'])
        else:
            entry['df'] = gui_get_df(sqobjs[entry['name']],
                                     namespace=[state.namespace],
                                     hostname=hostlist)
            pgbar.progress(progress + i*10)

    return faileddfs


def path_sidebar(state, sqobjs):
    """Configure sidebar"""

    devdf = gui_get_df(sqobjs['device'], columns=['namespace'])
    if devdf.empty:
        st.error('Unable to retrieve any namespace info')
        st.stop()

    namespaces = devdf.namespace.unique().tolist()
    if state.namespace:
        nsidx = namespaces.index(state.namespace)
    else:
        nsidx = 0
    ok_button = st.sidebar.button('Trace')
    namespace = st.sidebar.selectbox('Namespace',
                                     namespaces, index=nsidx,
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

    state.show_ifnames = st.sidebar.checkbox('Show in/out interface names',
                                             value=state.show_ifnames)
    if all(not x for x in [state.namespace,
                           state.source,
                           state.dest]):
        state.run = False
    elif ok_button:
        state.run = True
    elif namespace != state.namespace:
        state.run = False
        state.namespace = namespace

    return


def build_graphviz_obj(state: PathSessionState, df: pd.DataFrame,
                       faileddfs: FailedDFs):
    '''Return a graphviz object'''

    # The first order of business is to ensure we can draw the graph properly
    # Dot layout does the job in all scenarios except in some cases when the
    # hosts are out of step between multiple paths for only the first one or
    # two hops. Then, not selecting the layout is better than DOT.
    layout = 'dot'
    hostset = set()
    for i, hostgroup in enumerate(df.groupby(by=['hopCount'])
                                  .hostname.unique().tolist()):
        thisset = set(hostgroup)
        if hostset.intersection(thisset):
            layout = ''
        hostset = hostset.union(thisset)
        if i > 2:
            break

    graph_attr = {'splines': 'polyline'}
    if layout:
        graph_attr.update({'layout': layout})
    if state.show_ifnames:
        graph_attr.update({'nodesep': '1.0'})

    g = graphviz.Digraph(graph_attr=graph_attr,
                         node_attr={'URL': 'https://github.com/netenglabs/suzieq'})

    if layout == 'dot':
        for hostgroup in df.groupby(by=['hopCount']).hostname.unique().tolist():
            with g.subgraph() as s:
                s.attr(rank='same')
                for hostname in hostgroup:
                    s.node(hostname, style='filled')
    else:
        for host in df.hostname.unique().tolist():
            g.node(host, style='filled')

    pathid = 0
    prevrow = None
    connected_set = set()

    for row in df.itertuples():
        if row.pathid != pathid:
            prevrow = row
            pathid = row.pathid
            continue
        conn = (prevrow.hostname, row.hostname)
        if conn not in connected_set:
            if row.mtuMatch:
                if row.overlay:
                    # row.overlay is true if incoming packet is encap'ed
                    color = 'purple'
                elif prevrow.isL2:
                    color = 'blue'
                else:
                    color = 'black'
            else:
                color = 'red'

            tooltip = pd.DataFrame({
                'protocol': [prevrow.protocol],
                'lookup': [prevrow.lookup],
                'vrf': [prevrow.vrf],
                'mtu': [f'{prevrow.mtu} -> {row.mtu}'],
                'oif': [prevrow.oif],
                'iif': [row.iif]}).T.to_string()
            hname_str = quote(f'{prevrow.hostname} {row.hostname}')
            if_str = quote(f'ifname.isin(["{prevrow.oif}", "{row.iif}"])')
            ifURL = '&amp;'.join(['http://localhost:8501?page=Xplore',
                                  'table=interfaces',
                                  f'namespace={quote(state.namespace)}',
                                  'columns=default',
                                  f'hostname={hname_str}',
                                  f'query={if_str}',
                                  ])
            if state.show_ifnames:
                g.edge(prevrow.hostname, row.hostname, color=color,
                       label=str(row.hopCount), URL=ifURL,
                       tooltip=tooltip, taillabel=prevrow.oif,
                       headlabel=row.iif,
                       )
            else:
                g.edge(prevrow.hostname, row.hostname, color=color,
                       label=str(row.hopCount), edgeURL=ifURL,
                       edgetarget='_graphviz',
                       tooltip=tooltip
                       )

            connected_set.add(conn)
        prevrow = row
    return g


def page_work(state_container, page_flip: bool):
    '''Main workhorse routine for path'''

    if not state_container.pathSessionState:
        state_container.pathSessionState = PathSessionState()

    state = state_container.pathSessionState

    url_params = st.experimental_get_query_params()
    page = url_params.pop('page', '')
    if get_title() in page:
        if url_params and not all(not x for x in url_params.values()):
            url_params.pop('search_text', '')
            for key in url_params:
                val = url_params.get(key, '')
                if isinstance(val, list):
                    val = val[0]
                    url_params[key] = val
                if key == 'run':
                    if val == 'True':
                        url_params[key] = True
                    else:
                        url_params[key] = False

            state.__init__(**url_params)

    pgbar = st.empty()
    summary = st.beta_container()
    summcol, mid, pathcol = summary.beta_columns([3, 1, 10])
    with summary:
        with summcol:
            summ_ph = st.empty()
        with pathcol:
            fw_ph = st.empty()

    path_sidebar(state, state_container.sqobjs)

    if state.run:
        pgbar.progress(0)
        df, summ_df = path_get(state, forward_dir=True)
        pgbar.progress(40)
        # rev_df, _ = path_get(state, forward_dir=False)

    else:
        st.experimental_set_query_params(**asdict(state))
        st.stop()

    if df.empty:
        pgbar.progress(100)
        st.info(f'No path to trace between {state.source} and {state.dest}')
        st.experimental_set_query_params(**asdict(state))
        st.stop

    if not df.empty:
        faileddfs = get_failed_data(state, pgbar, df, state_container.sqobjs)
        g = build_graphviz_obj(state, df, faileddfs)
        pgbar.progress(100)
        # if not rev_df.empty:
        #     rev_g = build_graphviz_obj(state, rev_df)

        summ_ph.dataframe(data=summ_df)
        fw_ph.graphviz_chart(g, use_container_width=True)
        # rev_ph.graphviz_chart(rev_g, use_container_width=True)

        for entry in faileddfs.dfs:
            mdf = entry['df']
            if not mdf.empty:
                if entry['name'] == 'mlag':
                    mdf = mdf.query('mlagSinglePortsCnt != 0 or '
                                    ' mlagErrorPortsCnt != 0')
            table_expander = st.beta_expander(
                f'Failed {entry["name"]} Table', expanded=True)
            with table_expander:
                st.dataframe(mdf)

        table_expander = st.beta_expander('Path Table', expanded=True)
        with table_expander:
            st.dataframe(df)

    st.experimental_set_query_params(**asdict(state))
