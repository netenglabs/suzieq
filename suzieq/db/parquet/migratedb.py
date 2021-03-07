
from typing import Callable, Union
import pandas as pd
from pandas.core.computation.ops import UndefinedVariableError


def get_migrate_fn(table_name: str, from_vers: str,
                   to_vers: str) -> Union[Callable, None]:
    """Return a migration function if one is present for the table specified

    :param table_name: str, Name of the table for which we need the converter
    :param from_vers: str, Version number from which the conversion is needed
    :param to_vers: str, Version number to which the conversion is needed
    :returns: Routine to invoke to convert the data, or None
    :rtype: Callable or None

    """
    conversion_dict = {
        'bgp-1.0-2.0': _convert_bgp_vers_1_to_2
    }

    return conversion_dict.get(f'{table_name}-{from_vers}-{to_vers}', None)


def _convert_bgp_vers_1_to_2(df: pd.DataFrame) -> pd.DataFrame:
    """Convert BGP schema from version 1.0 to version 2.0

    The dataframe MUST contain the sqvers column

    """

    def set_community(x):
        communities = []
        if (x.afi != 'l2vpn'):
            return communities

        if x.evpnSendCommunity == 'extendedAndStandard':
            communities = ['standard', 'extended']
        elif x.evpnSendCommunity == 'extended':
            communities = ['extended']
        elif x.evpnSendCommunity == 'standard':
            communities = ['standard']
        return communities

    converted_df = pd.DataFrame()

    for pfx in ['v4', 'v6', 'evpn']:
        try:
            newdf = df.query(f'sqvers == "1.0" and {pfx}Enabled').reset_index()
        except UndefinedVariableError:
            newdf = pd.DataFrame()
        if not newdf.empty:
            if pfx == 'evpn':
                newdf['afi'] = 'l2vpn'
                newdf['safi'] = 'evpn'
            else:
                newdf['safi'] = 'unicast'
                if pfx == 'v4':
                    newdf['afi'] = 'ipv4'
                else:
                    newdf['afi'] = 'ipv6'

            newdf = newdf.rename(columns={
                f'{pfx}PfxRx': 'pfxRx',
                f'{pfx}PfxTx': 'pfxTx',
                f'{pfx}IngressRmap': 'ingressRmap',
                f'{pfx}EgressRmap': 'egressRmap',
                f'{pfx}defaultsent': 'defOriginate',
            })

            newdf['afisAdvOnly'] = [[] for _ in range(len(newdf))]
            newdf['afisRcvOnly'] = [[] for _ in range(len(newdf))]
            newdf['communityTypes'] = [[] for _ in range(len(newdf))]
            converted_df = pd.concat([converted_df, newdf])

    if not converted_df.empty:
        converted_df['afisAdvOnly'] += converted_df.apply(
            lambda x: ['ipv4 unicast']
            if (x.v4Advertised and not x.v4Received) else [], axis=1)
        converted_df['afisAdvOnly'] += converted_df.apply(
            lambda x: ['ipv6 unicast']
            if (x.v6Advertised and not x.v6Received) else [], axis=1)
        converted_df['afisAdvOnly'] += converted_df.apply(
            lambda x: ['l2vpn evpn']
            if (x.evpnAdvertised and not x.evpnReceived) else [], axis=1)

        converted_df['afisRcvOnly'] += converted_df.apply(
            lambda x: ['ipv4 unicast']
            if (not x.v4Advertised and x.v4Received) else [], axis=1)
        converted_df['afisRcvOnly'] += converted_df.apply(
            lambda x: ['ipv6 unicast']
            if (not x.v6Advertised and x.v6Received) else [], axis=1)
        converted_df['afisRcvOnly'] += converted_df.apply(
            lambda x: ['l2vpn evpn']
            if (not x.evpnAdvertised and x.evpnReceived) else [], axis=1)

        converted_df['communityTypes'] += converted_df.apply(set_community,
                                                             axis=1)

        converted_df['sqvers'] = '2.0'

        unconverted_df = df.query('sqvers != "1.0"').reset_index()
        final_df = pd.concat([converted_df, unconverted_df])

        return final_df.reset_index(drop=True)
    else:
        return df
