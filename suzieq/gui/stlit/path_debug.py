from itertools import zip_longest

import pandas as pd
import streamlit as st

from suzieq.gui.stlit.pagecls import SqGuiPage


class PathDebugPage(SqGuiPage):
    '''Page for Path trace page'''
    _title = 'Path-Debug'
    _state = None

    @property
    def add_to_menu(self) -> bool:
        return False

    def build(self):
        self._create_sidebar()
        self._render(None)

    def set_path_state(self, state):
        '''Save the path state from the Path window'''
        try:
            self._state = state._old_state['pages']['Path']
        except KeyError:
            self._state = state._new_session_state['pages']['Path']

    def _get_state_from_url(self):
        pass

    def _create_sidebar(self) -> None:
        st.sidebar.markdown("""Displays information from the various tables """
                            """used to build path""")

    def _create_layout(self) -> None:
        pass

    def _render(self, _) -> None:
        url_params = st.experimental_get_query_params()
        if url_params.get('lookupType', 'hop') == ['hop']:
            self._handle_hop_url(url_params)
        else:
            self._handle_edge_url(url_params)

    def _sync_state(self) -> None:
        pass

    def _save_page_url(self) -> None:
        pass

    # pylint: disable=too-many-statements
    def _handle_edge_url(self, url_params: dict):
        '''Display tables associated with a link'''

        namespace = url_params.get('namespace', [""])[0]
        hostname = url_params.get('hostname', [""])[0]
        nhip = url_params.get('nhip', [""])[0]
        ipLookup = url_params.get('ipLookup', [""])[0]
        vtepLookup = url_params.get('vtepLookup', [""])[0]
        vrf = url_params.get('vrf', [""])[0]
        ifhost = url_params.get('ifhost', [""])[0]
        macaddr = url_params.get('macaddr', [""])[0]
        oif = url_params.get('oif', [""])[0]

        state = self._state._state
        if not hostname:
            st.error('No hostname found to display information for')
            st.stop()

        st.header(f'Debug Tables for Path from {state.source} to '
                  f'{state.dest}')
        hoptype = 'Bridged' if macaddr else 'Routed'
        st.subheader(f'{hoptype} hop between {hostname} and {ifhost}')

        pathobj = getattr(self._state, '_pathobj', None)
        engobj = pathobj.engine

        if ipLookup:
            if not vtepLookup or (ipLookup != vtepLookup):
                st.info(f'Route Lookup on {hostname}')
                st.dataframe(data=engobj._rdf.query(
                    f'hostname=="{hostname}" and vrf=="{vrf}"'))

            if vtepLookup:
                st.info(f'Underlay Lookup on {hostname} for {vtepLookup}')
                vtepdf = engobj._underlay_dfs.get(vtepLookup,
                                                  pd.DataFrame())
                if not vtepdf.empty:
                    st.dataframe(data=vtepdf.query(
                        f'hostname=="{hostname}" and vrf=="default"'))
            if nhip:
                st.info(
                    f'ARP/ND Table on {hostname} for nexthop {nhip}, '
                    f'oif={oif}')
                arpdf = engobj._arpnd_df.query(f'hostname=="{hostname}" and '
                                               f'ipAddress=="{nhip}" and '
                                               f'oif=="{oif}"')
                st.dataframe(data=arpdf)

                if ':' in nhip:
                    dropcol = ['ipAddressList']
                else:
                    dropcol = ['ip6AddressList']
                if not arpdf.empty:
                    nhmac = arpdf.macaddr.iloc[0]
                    if nhmac:
                        if_df = engobj._if_df.query(f'macaddr=="{nhmac}" and '
                                                    f'hostname=="{ifhost}"') \
                                             .drop(columns=dropcol)
                        label = (f'matching nexthop {nhip}, '
                                 f'macaddr {nhmac} on '
                                 f'host {ifhost}')
                    else:
                        label = f'matching nexthop {nhip} on host {ifhost}'
                        if_df = engobj._if_df.query(f'hostname=="{ifhost}"') \
                                             .drop(columns=dropcol)
                else:
                    if_df = engobj._if_df.query(f'hostname=="{ifhost}"')\
                        .drop(columns=dropcol)
                    label = f'matching host {ifhost}'
                if nhip != '169.254.0.1':
                    st.info(f'Interfaces {label}')
                    s = if_df.ipAddressList.str \
                                           .startswith(f'{nhip}/') \
                                           .dropna()
                    s = s.loc[s]
                    st.dataframe(
                        data=engobj._if_df.iloc[s.loc[s].index])
                else:
                    st.info(f'Interfaces {label}')
                    st.dataframe(data=if_df)
        if macaddr:
            with st.expander(f'MAC Table for {hostname}, MAC addr {macaddr}',
                             expanded=True):
                st.dataframe(data=pathobj.engine._macsobj.get(
                    namespace=namespace, hostname=hostname, macaddr=macaddr))

    # pylint: disable=too-many-statements
    def _handle_hop_url(self, url_params):
        '''Handle table display associated with hop'''

        namespace = url_params.get('namespace', [""])[0]
        hostname = url_params.get('hostname', [""])[0]

        state = self._state._state
        if not hostname:
            st.error('No hostname found to display information for')
            st.stop()

        st.header(f'Debug Tables for Path from {state.source} to '
                  f'{state.dest}')

        failed_dfs = getattr(self._state, '_failed_dfs', None)
        for tbl, fdf in failed_dfs.items():
            if not fdf.empty:
                this_df = fdf.query(f'namespace=="{namespace}" and '
                                    f'hostname=="{hostname}"')
                if this_df.empty:
                    continue
                table_expander = st.expander(
                    f'Failed {tbl} Table', expanded=not fdf.empty)
                table_expander.dataframe(fdf)

        pathobj = getattr(self._state, '_pathobj', None)
        df = getattr(self._state, '_path_df', None)
        engobj = pathobj.engine

        if df.empty:
            st.warning('Empty path dataframe')
            st.stop()

        host_dfg = df.query(f'hostname == "{hostname}"') \
                     .groupby(by=['hopCount'])

        df2 = host_dfg.agg({'vrf': ['unique'], 'ipLookup': ['unique'],
                            'nexthopIp': ['unique'], 'oif': ['unique'],
                            'macLookup': ['unique'],
                            'vtepLookup': ['unique']}).reset_index()
        df2.columns = ['hopCount', 'vrf', 'ipLookup', 'nexthopIp', 'oif',
                       'macaddr', 'vtepLookup']
        df2 = df2.explode('hopCount').explode('vrf').explode('ipLookup') \
                                                    .explode('macaddr') \
                                                    .explode('vtepLookup')
        df2.drop_duplicates(subset=['vrf', 'ipLookup'], inplace=True)

        for row in df2.itertuples():
            with st.expander(f'Lookups on {hostname}, for hopcount: '
                             f'{row.hopCount}', expanded=True):
                if row.macaddr:
                    st.info(f'MAC Table on {hostname}, MAC addr {row.macaddr}')
                    st.dataframe(data=engobj._macsobj.get(namespace=namespace,
                                                          hostname=hostname,
                                                          macaddr=row.macaddr))
                    continue

                if (row.ipLookup != row.vtepLookup):
                    st.info(f'Route Lookup on {hostname}')
                    st.dataframe(data=engobj._rdf.query(
                        f'hostname=="{hostname}" and vrf=="{row.vrf}"'))

                if row.vtepLookup:
                    st.info(
                        f'Underlay Lookup on {hostname} for {row.vtepLookup}')
                    vtepdf = engobj._underlay_dfs.get(row.vtepLookup,
                                                      pd.DataFrame())
                    if not vtepdf.empty:
                        st.dataframe(data=vtepdf.query(
                            f'hostname=="{hostname}" and vrf=="default"'))

                oifs = row.oif.tolist()
                nhops = row.nexthopIp.tolist()
                prev_nhop = ''
                for oif, nhop in zip_longest(oifs, nhops):
                    _, arpcol = st.columns([1, 40])
                    _, ifcol = st.columns([2, 40])
                    # this logic because I don't know what fn to use with agg
                    # above to not remove non-unique nhop.
                    if not nhop and prev_nhop:
                        nhop = prev_nhop
                    else:
                        prev_nhop = nhop
                    arpdf = engobj._arpnd_df.query(
                        f'hostname=="{hostname}" '
                        f' and ipAddress=="{nhop}" and '
                        f'oif=="{oif}"')
                    with arpcol:
                        st.info(f'ARP/ND Lookup on {hostname} for {nhop}')
                        st.dataframe(data=arpdf, height=100)

                    if not arpdf.empty:
                        if ':' in nhop:
                            dropcol = ['ipAddressList']
                        else:
                            dropcol = ['ip6AddressList']
                        if nhop == '169.254.0.1':
                            macaddr = arpdf.macaddr.iloc[0]
                            if_df = engobj._if_df.query(
                                f'macaddr=="{macaddr}"') \
                                .drop(columns=dropcol)
                            label = f'matching nexthop {nhop}, '\
                                f'macaddr {macaddr}'
                        else:
                            if_df = engobj._if_df.drop(columns=dropcol)
                            label = f'matching nexthop {nhop}'
                    else:
                        label = f'matching nexthop {nhop}'
                        if_df = engobj._if_df
                    if ':' in nhop:
                        s = if_df.ip6AddressList \
                                 .explode() \
                                 .str.startswith(f'{nhop}/').dropna()
                        s = s.loc[s]
                        if_df = if_df.iloc[s.loc[s].index]
                    elif nhop != '169.254.0.1':
                        s = if_df.ipAddressList \
                                 .explode() \
                                 .str.startswith(f'{nhop}/').dropna()
                        s = s.loc[s]
                        if_df = if_df.iloc[s.loc[s].index]
                    with ifcol:
                        st.info(f'Interfaces {label}')
                        st.dataframe(data=if_df, height=600)
            st.markdown("<hr>", unsafe_allow_html=True)
