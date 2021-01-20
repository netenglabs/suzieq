from itertools import zip_longest

import pandas as pd
import streamlit as st


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
    ipLookup = url_params.get('ipLookup', [""])[0]
    vtepLookup = url_params.get('vtepLookup', [""])[0]
    vrf = url_params.get('vrf', [""])[0]
    ifhost = url_params.get('ifhost', [""])[0]
    macaddr = url_params.get('macaddr', [""])[0]
    oif = url_params.get('oif', [""])[0]

    if not hostname:
        st.error('No hostname found to display information for')
        st.stop()

    st.header(f'Debug Tables for Path from {pathSession.source} to '
              f'{pathSession.dest}')
    hoptype = 'Bridged' if macaddr else 'Routed'
    st.subheader(f'{hoptype} hop between {hostname} and {ifhost}')

    pathobj = getattr(pathSession, 'pathobj', None)
    engobj = pathobj.engine_obj

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
                f'ARP/ND Table on {hostname} for nexthop {nhip}, oif={oif}')
            arpdf = engobj._arpnd_df.query(f'hostname=="{hostname}" and '
                                           f'ipAddress=="{nhip}" and '
                                           f'oif=="{oif}"')
            st.dataframe(data=arpdf)

            if not arpdf.empty:
                if ':' in nhip:
                    dropcol = ['ipAddressList']
                else:
                    dropcol = ['ip6AddressList']

                nhmac = arpdf.macaddr.iloc[0]
                if nhmac:
                    if_df = engobj._if_df.query(f'macaddr=="{nhmac}" and '
                                                f'hostname=="{ifhost}"') \
                                         .drop(columns=dropcol)
                    label = (f'matching nexthop {nhip}, macaddr {nhmac} on '
                             f'host {ifhost}')
                else:
                    label = f'matching nexthop {nhip} on host {ifhost}'
                    if_df = engobj._if_df.query(f'hostname=="{ifhost}"') \
                                         .drop(columns=dropcol)

            if nhip != '169.254.0.1':
                st.info(f'Interfaces {label}')
                s = if_df.ipAddressList.str \
                                       .startswith(f'{nhip}/') \
                                       .dropna()
                s = s.loc[s == True]
                st.dataframe(data=engobj._if_df.iloc[s.loc[s == True].index])
            else:
                st.info(f'Interfaces {label}')
                st.dataframe(data=if_df)
    if macaddr:
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

    pathobj = getattr(pathSession, 'pathobj', None)
    df = getattr(pathSession, 'path_df', None)
    engobj = pathobj.engine_obj

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
        with st.beta_expander(f'Lookups on {hostname}, for hopcount: '
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
                st.info(f'Underlay Lookup on {hostname} for {row.vtepLookup}')
                vtepdf = engobj._underlay_dfs.get(row.vtepLookup,
                                                  pd.DataFrame())
                if not vtepdf.empty:
                    st.dataframe(data=vtepdf.query(
                        f'hostname=="{hostname}" and vrf=="default"'))

            oifs = row.oif.tolist()
            nhops = row.nexthopIp.tolist()
            prev_nhop = ''
            for oif, nhop in zip_longest(oifs, nhops):
                blank1, arpcol = st.beta_columns([1, 40])
                blank2, ifcol = st.beta_columns([2, 40])
                # this logic because I don't know what fn to use with agg above
                # to not remove non-unique nhop.
                if not nhop and prev_nhop:
                    nhop = prev_nhop
                else:
                    prev_nhop = nhop
                arpdf = engobj._arpnd_df.query(f'hostname=="{hostname}" and '
                                               f'ipAddress=="{nhop}" and '
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
                        if_df = engobj._if_df.query(f'macaddr=="{macaddr}"') \
                                             .drop(columns=dropcol)
                        label = f'matching nexthop {nhop}, macaddr {macaddr}'
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
                    s = s.loc[s == True]
                    if_df = if_df.iloc[s.loc[s == True].index]
                elif nhop != '169.254.0.1':
                    s = if_df.ipAddressList \
                             .explode() \
                             .str.startswith(f'{nhop}/').dropna()
                    s = s.loc[s == True]
                    if_df = if_df.iloc[s.loc[s == True].index]
                with ifcol:
                    st.info(f'Interfaces {label}')
                    st.dataframe(data=if_df, height=600)
        st.markdown("<hr>", unsafe_allow_html=True)


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
