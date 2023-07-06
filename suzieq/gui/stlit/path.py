from dataclasses import dataclass
from typing import Tuple
from urllib.parse import quote

import pandas as pd
import streamlit as st
import graphviz
from st_aggrid import (GridOptionsBuilder, AgGrid, GridUpdateMode,
                       JsCode)

from suzieq.sqobjects import get_sqobject
from suzieq.gui.stlit.guiutils import (gui_get_df, set_def_aggrid_options,
                                       display_help_icon,
                                       get_session_id, SuzieqMainPages)
from suzieq.gui.stlit.pagecls import SqGuiPage


@dataclass
class PathSessionState:
    '''Session state for status page'''
    page: str = SuzieqMainPages.PATH.value
    namespace: str = ''
    source: str = ''
    dest: str = ''
    start_time: str = ''
    end_time: str = ''
    show_ifnames: bool = False
    vrf: str = ''


class PathPage(SqGuiPage):
    '''Page for Path trace page'''
    _title: str = SuzieqMainPages.PATH.value
    _state: PathSessionState = PathSessionState()
    _failed_dfs = {}
    _pathobj = None
    _path_df: pd.DataFrame = None
    _config_file: str = st.session_state.get('config_file', '')

    @property
    def add_to_menu(self) -> bool:
        return True

    def build(self):
        self._get_state_from_url()
        self._create_sidebar()
        layout = self._create_layout()
        self._render(layout)

    def _create_layout(self) -> dict:

        pgbar = st.empty()
        summary = st.container()
        summcol, _, pathcol = summary.columns([3, 1, 10])
        with summary:
            with summcol:
                summ_ph = st.empty()
                legend_ph = st.container()
            with pathcol:
                fw_ph = st.empty()
        table_expander = st.empty()
        failed_tables = st.empty()
        return ({
            'pgbar': pgbar,
            'summary': summ_ph,
            'legend': legend_ph,
            'fw_path': fw_ph,
            'table': table_expander,
            'failed_tables': failed_tables,
        })

    def _create_sidebar(self) -> None:

        state = self._state
        devdf = gui_get_df('device', config_file=self._config_file,
                           columns=['namespace'])
        if devdf.empty:
            st.error('Unable to retrieve any namespace info')
            st.stop()

        namespaces = [''] + sorted(devdf.namespace.unique().tolist())

        nsidx = 0
        if state.namespace and state.namespace in namespaces:
            nsidx = namespaces.index(state.namespace)

        url = '&amp;'.join([
            f'?page=Help&session={get_session_id()}',
            'help=yes',
            'help_on=Path',
        ])
        display_help_icon(url)
        with st.sidebar:
            with st.form(key='trace'):
                state.namespace = st.selectbox(
                    'Namespace', namespaces, key='path_namespace',
                    index=nsidx)
                state.source = st.text_input('Source IP',
                                             key='path_source',
                                             value=state.source)
                state.dest = st.text_input('Dest IP', value=state.dest,
                                           key='path_dest')

                state.vrf = st.text_input('VRF', value=state.vrf,
                                          key='path_vrf')
                state.start_time = st.text_input('Start Time',
                                                 value=state.start_time,
                                                 key='path_start_time')
                state.end_time = st.text_input('End Time',
                                               value=state.end_time,
                                               key='path_end_time')

                _ = st.form_submit_button('Trace', on_click=self._sync_state)

            state.show_ifnames = st.checkbox('Show in/out interface names',
                                             value=state.show_ifnames,
                                             key='path_show_ifnames',
                                             on_change=self._sync_state)
            _ = st.button(
                'Source <-> Dest', key='path_swap',
                on_click=self._swap_src_dest)

    def _swap_src_dest(self):
        state = self._state
        state.source, state.dest = state.dest, state.source
        self._sync_state()

    def _sync_state(self) -> None:
        wsstate = st.session_state
        state = self._state

        state.namespace = wsstate.path_namespace
        state.vrf = wsstate.path_vrf
        state.start_time = wsstate.path_start_time
        state.end_time = wsstate.path_end_time
        state.show_ifnames = wsstate.path_show_ifnames
        self._save_page_url()

    def _render(self, layout: dict) -> None:
        '''Compute the path, render all objects'''

        state = self._state
        missing = [x for x in [state.source,
                               state.dest, state.namespace] if not x]
        if missing:
            st.warning('Set namespace, source and destination in the sidebar '
                       'to do a path trace ')
            st.stop()

        layout['pgbar'].progress(0)
        self._pathobj = get_sqobject(
            'path')(config_file=self._config_file,
                    start_time=state.start_time,
                    end_time=state.end_time)
        try:
            df, summ_df = self._get_path(forward_dir=True)
            rdf = getattr(self._pathobj.engine, '_rdf', pd.DataFrame())
            if not rdf.empty:
                # Something did get computed
                self._path_df = df
        except Exception as e:  # pylint: disable=broad-except
            st.error(f'Invalid Input: {str(e)}')
            layout['pgbar'].progress(100)
            self._path_df = pd.DataFrame()
            st.stop()
            return

        layout['pgbar'].progress(40)

        if df.empty:
            layout['pgbar'].progress(100)
            st.info(f'No path to trace between {self._state.source} and '
                    f'{self._state.dest}')
            st.stop()
            return

        self._get_failed_data(state.namespace, layout['pgbar'])

        g = self._build_graphviz_obj(state.show_ifnames, df)
        layout['pgbar'].progress(100)
        # if not rev_df.empty:
        #     rev_g = build_graphviz_obj(state, rev_df)

        layout['summary'].dataframe(data=summ_df.astype(str))
        with layout['legend']:
            st.info('''Color Legend''')
            st.markdown('''
<b style="color:blue">Blue Lines</b> => L2 Hop(non-tunneled)<br>
<b>Black Lines</b> => L3 Hop<br>
<b style="color:purple">Purple lines</b> => Tunneled Hop<br>
<b style="color:red">Red Lines</b> => Hops with Error<br>
''', unsafe_allow_html=True)

        layout['fw_path'].graphviz_chart(g, use_container_width=True)
        # rev_ph.graphviz_chart(rev_g, use_container_width=True)

        with layout['table']:
            table_expander = st.expander('Path Table', expanded=True)
            with table_expander:
                self._draw_aggrid_df(df)

    def _draw_aggrid_df(self, df):

        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(paginationPageSize=25)

        gb.configure_default_column(floatingFilter=True)
        if 'error' in df.columns:
            jscode = self._aggrid_style()
            gb.configure_column("error", floatingFilter=True,
                                cellStyle=jscode, editable=False)

        gb.configure_grid_options(
            domLayout='normal', preventDefaultOnContextMenu=True)

        gridOptions = gb.build()
        gridOptions = set_def_aggrid_options(gridOptions)
        gridOptions['getRowStyle'] = self._aggrid_style_rows(df)

        _ = AgGrid(
            df,
            gridOptions=gridOptions,
            allow_unsafe_jscode=True,
            update_mode=GridUpdateMode.NO_UPDATE,
            theme='streamlit',
        )

    def _aggrid_style_rows(self, df: pd.DataFrame):
        '''Style the cells based on value'''

        if 'error' in df.columns:
            a = """
                function(params) {
                    if (params.data.error !== '') {
                        return {
                            'color': 'white',
                            'backgroundColor': 'red'
                        }
                    }
                };
                """
        else:
            a = """
            function(params) {
                    return {
                        'backgroundColor': 'white'
                    }
            };
            """
        return JsCode(a)

    def _get_path(self, forward_dir: bool = True) -> Tuple[pd.DataFrame,
                                                           pd.DataFrame]:
        '''Get path & summary df'''
        if forward_dir:
            df = self._pathobj.get(namespace=[self._state.namespace],
                                   src=self._state.source,
                                   dest=self._state.dest,
                                   vrf=self._state.vrf)

            summ_df = self._path_summarize(df)
        return df, summ_df

    def _get_failed_data(self, namespace: str, pgbar) -> None:
        '''Get interface/mlag/routing protocol states that are failed'''

        progress = 40
        for i, entry in enumerate([
                {'name': 'device', 'query': 'status == "dead"'},
                {'name': 'interfaces',
                 'query': 'state == "down" and adminState == "up"'},
                {'name': 'mlag',
                 'query': '(state != "active") or (mlagSinglePortsCnt != 0 or '
                 'mlagErrorPortsCnt != 0)'},
                {'name': 'ospf', 'query': 'adjState == "other"'},
                {'name': 'bgp', 'query': 'state == "NotEstd"'}
        ]):
            df = gui_get_df(
                entry['name'], self._config_file, namespace=[namespace])
            if not df.empty and (entry.get('query', '')):
                df = df.query(entry['query']).reset_index(drop=True)
                self._failed_dfs[entry['name']] = df
            pgbar.progress(progress + i*10)

    def _path_summarize(self, path_df: pd.DataFrame) -> pd.DataFrame:
        '''Summarizes the path, a copy of the function in pandas/path.py

        Until we support a mechanism to avoid running path twice to get
        a summary, this is the best we can do to avoid running path twice
        '''

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
        ns[namespace]['pathMtu'] = min(
            path_df.query('iif != "lo"')['inMtu'].min(),
            path_df.query('iif != "lo"')['outMtu'].min())

        summary_fields = ['totalPaths', 'perHopEcmp', 'maxPathLength',
                          'avgPathLength', 'uniqueDevices', 'pathMtu',
                          'usesOverlay', 'mtuMismatch']
        return pd.DataFrame(ns).reindex(summary_fields, axis=0) \
                               .convert_dtypes()

    # pylint: disable=too-many-statements
    @st.cache(max_entries=10, allow_output_mutation=True)
    def _build_graphviz_obj(self, show_ifnames: bool, df: pd.DataFrame):
        '''Return a graphviz object'''

        graph_attr = {'splines': 'polyline', 'layout': 'dot'}
        if show_ifnames:
            graph_attr.update({'nodesep': '1.0'})

        g = graphviz.Digraph(graph_attr=graph_attr,
                             name='Hover over arrow head for edge info')

        hostset = set()
        for hostgroup in df.groupby(by=['hopCount']) \
                           .hostname.unique().tolist():
            with g.subgraph() as s:
                s.attr(rank='same')
                for hostname in hostgroup:
                    if hostname in hostset:
                        continue
                    hostset.add(hostname)
                    debugURL = '&amp;'.join([
                        f'?page={quote("Path-Debug")}',
                        'lookupType=hop',
                        f'namespace={quote(df.namespace[0])}',
                        f'session={quote(get_session_id())}',
                        f'hostname={quote(hostname)}',
                    ])
                    tooltip, color = self._get_node_tooltip_color(
                        hostname)
                    s.node(hostname, tooltip=tooltip, color=color,
                           URL=debugURL, target='_graphviz', shape='box')

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
                    f'?page={quote("Path-Debug")}',
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

    def _get_node_tooltip_color(self, hostname: str) -> str:
        '''Get tooltip and node color for node based on various tables'''

        ttip = {'title': ['Failed entry count']}
        for tbl, df in self._failed_dfs.items():
            ttip.update({tbl: [df.loc[df.hostname == hostname]
                               .hostname.count()]})
        tdf = pd.DataFrame(ttip)
        if tdf.select_dtypes(include='int64').max().max() > 0:
            color = 'red'
        else:
            color = 'black'
        return ('\n'.join(tdf.T.to_string().split('\n')[1:]), color)

    def _aggrid_style(self):
        '''Style the cells based on value'''
        a = """
            function(params) {
                if (params.error != '') {
                    return {
                        'color': 'white',
                        'backgroundColor': 'darkred'
                    }
                }
            };
            """
        return JsCode(a)

    @staticmethod
    def _highlight_erroneous_rows(row):
        '''Highlight rows with error in them'''
        if getattr(row, 'error', '') != '':
            return ["background-color: red; color: white"]*len(row)
        else:
            return [""]*len(row)
