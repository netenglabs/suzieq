from suzieq.gui.guiutils import display_help_icon
from suzieq.gui.guiutils import gui_get_df, get_base_url, get_session_id
from suzieq.sqobjects.path import PathObj
from copy import copy
from urllib.parse import quote
import graphviz as graphviz
import pandas as pd
import streamlit as st
from dataclasses import dataclass, asdict, field


def get_title():
    return 'Path'


def make_fields_failed_df():
    '''return a dictionary as this is the only way dataclassses work'''

    return [
        {'name': 'device', 'df': pd.DataFrame(), 'query': 'status == "dead"'},
        {'name': 'interfaces', 'df': pd.DataFrame(), 'query': 'state == "down"'},
        {'name': 'mlag', 'df': pd.DataFrame(),
         'query': 'mlagSinglePortsCnt != 0 or mlagErrorPortsCnt != 0'},
        {'name': 'ospf', 'df': pd.DataFrame(), 'query': 'adjState == "other"'},
        {'name': 'bgp', 'df': pd.DataFrame(), 'query': 'state == "NotEstd"'}
    ]


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
    pathobj: PathObj = None
    path_df: pd.DataFrame = None


@dataclass
class FailedDFs:
    dfs: list = field(default_factory=make_fields_failed_df)


def get_path_url_params(state: PathSessionState):
    '''Return the list of valid query params for path URL'''
    state_dict = copy(asdict(state))
    del state_dict['pathobj']
    del state_dict['path_df']

    return state_dict


def gui_path_summarize(path_df: pd.DataFrame) -> pd.DataFrame:
    '''Summarizes the path, a copy of the function in pandas/path.py'''

    if path_df.empty:
        return pd.DataFrame()

    namespace = path_df.namespace.iloc[0]
    ns = {}
    ns[namespace] = {}

    perhopEcmp = path_df.query('hopCount != 0') \
                        .groupby(by=['hopCount'])['hostname']
    ns[namespace]['totalPaths'] = path_df['pathid'].max()
    ns[namespace]['perHopEcmp'] = perhopEcmp.nunique().tolist()
    ns[namespace]['maxPathLength'] = path_df.groupby(by=['pathid'])[
        'hopCount'].max().max()
    ns[namespace]['avgPathLength'] = path_df.groupby(by=['pathid'])[
        'hopCount'].max().mean()
    ns[namespace]['uniqueDevices'] = path_df['hostname'].nunique()
    ns[namespace]['mtuMismatch'] = not all(path_df['mtuMatch'])
    ns[namespace]['usesOverlay'] = any(path_df['overlay'])
    ns[namespace]['pathMtu'] = min(path_df.query('iif != "lo"')['inMtu'].min(),
                                   path_df.query('iif != "lo"')['outMtu'].min())

    summary_fields = ['totalPaths', 'perHopEcmp', 'maxPathLength',
                      'avgPathLength', 'uniqueDevices', 'pathMtu',
                      'usesOverlay', 'mtuMismatch']
    return pd.DataFrame(ns).reindex(summary_fields, axis=0) \
                           .convert_dtypes()


def highlight_erroneous_rows(row):
    '''Highlight rows with error in them'''
    if getattr(row, 'error', '') != '':
        return [f"background-color: red; color: white"]*len(row)
    else:
        return [""]*len(row)


@st.cache(ttl=120, allow_output_mutation=True, show_spinner=False,
          max_entries=10)
def path_get(state: PathSessionState, pathobj: PathObj,
             forward_dir: bool) -> (pd.DataFrame, pd.DataFrame):
    '''Run the path and return the dataframes'''
    if forward_dir:
        df = pathobj.get(namespace=[state.namespace], source=state.source,
                         dest=state.dest, vrf=state.vrf)

        summ_df = gui_path_summarize(df)
    return df, summ_df


@st.cache(ttl=120, allow_output_mutation=True, show_spinner=False,
          hash_funcs={"streamlit.delta_generator.DeltaGenerator": lambda x: 1},
          max_entries=10)
def get_failed_data(namespace: str, pgbar, sqobjs) -> FailedDFs:
    '''Get interface/mlag/routing protocol states that are failed'''

    faileddfs = FailedDFs()

    progress = 40
    for i, entry in enumerate(faileddfs.dfs):
        entry['df'] = gui_get_df(sqobjs[entry['name']],
                                 namespace=[namespace])
        if not entry['df'].empty and (entry.get('query', '')):
            entry['df'] = entry['df'].query(entry['query'])

        pgbar.progress(progress + i*10)

    return faileddfs


def path_sidebar(state, sqobjs):
    """Configure sidebar"""

    devdf = gui_get_df(sqobjs['device'], columns=['namespace'])
    if devdf.empty:
        st.error('Unable to retrieve any namespace info')
        st.stop()

    namespaces = sorted(devdf.namespace.unique().tolist())
    if state.namespace:
        nsidx = namespaces.index(state.namespace)
    else:
        nsidx = 0

    url = '&amp;'.join([
        f'{get_base_url()}?page=_Help_',
        'help=yes',
        'help_on=Path',
    ])
    display_help_icon(url)
    ok_button = st.sidebar.button('Trace')
    namespace = st.sidebar.selectbox('Namespace',
                                     namespaces, index=nsidx)
    src_ph = st.sidebar.empty()
    dst_ph = st.sidebar.empty()
    state.source = src_ph.text_input('Source IP',
                                     value=state.source)
    state.dest = dst_ph.text_input('Dest IP', value=state.dest,
                                   key='dest')
    swap_src_dest = st.sidebar.button('Source <-> Dest')
    if swap_src_dest:
        source = src_ph.text_input('Source IP',
                                   value=state.dest)
        dest = dst_ph.text_input('Dest IP', value=state.source)
        state.source = source
        state.dest = dest

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


def get_node_tooltip_color(hostname: str, faileddfs: FailedDFs) -> str:
    '''Get tooltip and node color for node based on values in various tables'''

    ttip = {'title': ['Failed entry count']}
    for entry in faileddfs.dfs:
        mdf = entry['df']
        ttip.update({entry['name']: [mdf.loc[mdf.hostname == hostname]
                                     .hostname.count()]})
    tdf = pd.DataFrame(ttip)
    if tdf.select_dtypes(include='int64').max().max() > 0:
        color = 'red'
    else:
        color = 'black'
    return('\n'.join(tdf.T.to_string().split('\n')[1:]), color)


@st.cache(max_entries=10, allow_output_mutation=True)
def build_graphviz_obj(show_ifnames: bool, df: pd.DataFrame,
                       faileddfs: FailedDFs):
    '''Return a graphviz object'''

    graph_attr = {'splines': 'polyline', 'layout': 'dot'}
    if show_ifnames:
        graph_attr.update({'nodesep': '1.0'})

    g = graphviz.Digraph(graph_attr=graph_attr,
                         name='Hover over arrow head for edge info')

    hostset = set()
    for hostgroup in df.groupby(by=['hopCount']).hostname.unique().tolist():
        with g.subgraph() as s:
            s.attr(rank='same')
            for hostname in hostgroup:
                if hostname in hostset:
                    continue
                hostset.add(hostname)
                debugURL = '&amp;'.join([
                    f'{get_base_url()}?page={quote("_Path_Debug_")}',
                    'lookupType=hop',
                    f'namespace={quote(df.namespace.unique().tolist()[0])}',
                    f'session={quote(get_session_id())}',
                    f'hostname={quote(hostname)}',
                ])
                tooltip, color = get_node_tooltip_color(hostname, faileddfs)
                s.node(hostname, tooltip=tooltip, color=color, URL=debugURL,
                       target='_graphviz', shape='box')

    pathid = 0
    prevrow = None
    connected_set = set()

    df['nextPathid'] = df.pathid.shift(-1).fillna('0').astype(int)
    for row in df.itertuples():
        if row.pathid != pathid:
            prevrow = row
            pathid = row.pathid
            continue
        conn = (prevrow.hostname, row.hostname)
        if conn not in connected_set:
            if row.overlay:
                path_type = 'underlay'
                color = 'purple'
            elif prevrow.isL2:
                path_type = 'l2'
                color = 'blue'
            else:
                path_type = 'l3'
                color = 'black'

            if not row.mtuMatch:
                color = 'red'
                error = 'MTU mismatch'
                err_pfx = ', '
            else:
                error = ''
                err_pfx = ''

            tdf = pd.DataFrame({
                'pathType': path_type,
                'protocol': [prevrow.protocol],
                'ipLookup': [prevrow.ipLookup],
                'vtepLookup': [prevrow.vtepLookup],
                'macLookup': [prevrow.macLookup],
                'nexthopIp': [prevrow.nexthopIp],
                'vrf': [prevrow.vrf],
                'mtu': [f'{prevrow.outMtu} -> {row.inMtu}'],
                'oif': [prevrow.oif],
                'iif': [row.iif]})
            rowerr = getattr(prevrow, 'error', '')
            if rowerr:
                error += f"{err_pfx}{rowerr}"
            if error:
                err_pfx = ', '
            if row.nextPathid != row.pathid:
                # We need to capture any errors on the dest node as well
                destnode_error = getattr(row, 'error', '')
                if destnode_error:
                    error += f'{err_pfx}{destnode_error}'

            if error:
                tdf['error'] = error
                color = 'red'
            tooltip = '\n'.join(tdf.T.to_string(
                justify='right').split('\n')[1:])
            debugURL = '&amp;'.join([
                f'{get_base_url()}?page={quote("_Path_Debug_")}',
                'lookupType=edge',
                f'namespace={quote(row.namespace)}',
                f'session={quote(get_session_id())}',
                f'hostname={quote(prevrow.hostname)}',
                f'vrf={quote(prevrow.vrf)}',
                f'vtepLookup-{prevrow.vtepLookup}',
                f'ifhost={quote(row.hostname)}',
                f'ipLookup={quote(prevrow.ipLookup)}',
                f'oif={quote(prevrow.oif)}',
                f'macaddr={quote(prevrow.macLookup or "")}',
                f'nhip={quote(prevrow.nexthopIp)}',
            ])
            if show_ifnames:
                g.edge(prevrow.hostname, row.hostname, color=color,
                       label=str(row.hopCount), URL=debugURL,
                       edgetarget='_graphviz', tooltip=tooltip,
                       taillabel=prevrow.oif, headlabel=row.iif,
                       penwidth='2.0',
                       )
            else:
                g.edge(prevrow.hostname, row.hostname, color=color,
                       label=str(row.hopCount), URL=debugURL,
                       edgetarget='_graphviz', penwidth='2.0',
                       tooltip=tooltip
                       )

            connected_set.add(conn)
        prevrow = row
    df.drop(columns=['nextPathid'], inplace=True, errors='ignore')
    return g


def page_work(state_container, page_flip: bool):
    '''Main workhorse routine for path'''

    if not state_container.pathSessionState:
        state_container.pathSessionState = PathSessionState()

    state = state_container.pathSessionState

    url_params = st.experimental_get_query_params()
    page = url_params.pop('page', '')

    if not state and get_title() in page:
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
    state_container.pathSessionState = state

    pgbar = st.empty()
    summary = st.beta_container()
    summcol, mid, pathcol = summary.beta_columns([3, 1, 10])
    with summary:
        with summcol:
            summ_ph = st.empty()
            legend_ph = st.beta_container()
        with pathcol:
            fw_ph = st.empty()

    path_sidebar(state, state_container.sqobjs)

    if state.run:
        pgbar.progress(0)
        pathobj = PathObj(start_time=state.start_time,
                          end_time=state.end_time)
        try:
            df, summ_df = path_get(state, pathobj, forward_dir=True)
            rdf = getattr(pathobj.engine, '_rdf', pd.DataFrame())
            if not rdf.empty:
                state.pathobj = pathobj
                state.path_df = df
        except Exception as e:
            st.error(f'Invalid Input: {str(e)}')
            st.stop()
        pgbar.progress(40)
        # rev_df, _ = path_get(state, forward_dir=False)

    else:
        st.experimental_set_query_params(**get_path_url_params(state))
        st.stop()

    if df.empty:
        pgbar.progress(100)
        st.info(f'No path to trace between {state.source} and {state.dest}')
        st.experimental_set_query_params(**get_path_url_params(state))
        st.stop

    if not df.empty:
        faileddfs = get_failed_data(state.namespace, pgbar,
                                    state_container.sqobjs)
        g = build_graphviz_obj(state.show_ifnames, df, faileddfs)
        pgbar.progress(100)
        # if not rev_df.empty:
        #     rev_g = build_graphviz_obj(state, rev_df)

        summ_ph.dataframe(data=summ_df)
        with legend_ph:
            st.info('''Color Legend''')
            st.markdown('''
<b style="color:blue">Blue Lines</b> => L2 Hop(non-tunneled)<br>
<b>Black Lines</b> => L3 Hop<br>
<b style="color:purple">Purple lines</b> => Tunneled Hop<br>
<b style="color:red">Red Lines</b> => Hops with Error<br>
''', unsafe_allow_html=True)

        fw_ph.graphviz_chart(g, use_container_width=True)
        # rev_ph.graphviz_chart(rev_g, use_container_width=True)

        for entry in faileddfs.dfs:
            mdf = entry['df']
            table_expander = st.beta_expander(
                f'Failed {entry["name"]} Table', expanded=not mdf.empty)
            with table_expander:
                st.dataframe(mdf)

        table_expander = st.beta_expander('Path Table', expanded=True)
        with table_expander:
            st.dataframe(data=df.style.apply(highlight_erroneous_rows, axis=1),
                         height=600)

    st.experimental_set_query_params(**get_path_url_params(state))
