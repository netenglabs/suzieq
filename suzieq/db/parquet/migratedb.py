
from typing import Callable, Union
import pandas as pd
from pandas.errors import UndefinedVariableError
from suzieq.shared.exceptions import SqVersConversionError
from suzieq.shared.schema import Schema

from suzieq.shared.utils import get_default_per_vals


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


def generic_migration(df: pd.DataFrame, table: str,
                      schema: Schema) -> pd.DataFrame:
    """The generic migration fuction tries to perform the conversion from an
    old schema to the new one:
      - Creating the missing fields and writing a default value
      - Checking if there are type mismatches and try a simple conversion
      - Removing all the fields which are not in the schema anymore
    This function allows to perform automatic conversion whenever possible,
    to perform more complex actions we need a specific conversion function.

    Args:
        df (pd.DataFrame): DataFrame to migrate
        schema (Schema): the current schema

    Returns:
        pd.DataFrame: the migrated DataFrame
    """

    # Try generic conversion of the dataframe
    arrow_schema = schema.get_arrow_schema()
    defaults = get_default_per_vals()
    missing_fields = [f for f in arrow_schema
                      if f.name not in df.columns]
    for column in missing_fields:
        field_info = schema.field(column.name)
        if field_info:
            default_val = field_info.get('default',
                                         defaults.get(column.type, ''))
        else:
            default_val = defaults.get(column.type, '')
        df[column.name] = default_val

    # convert all dtypes to whatever is desired
    columns_in_schema = arrow_schema.names
    for column in columns_in_schema:
        # If the column was missing, there is no need to try conversion, since
        # there is no previous type
        if column not in missing_fields:
            schema_type = arrow_schema.field(column).type.to_pandas_dtype()
            if df.dtypes[column] != schema_type:
                # when conversion can't be automatically performed we need to
                # write a specific migration fn. Reraise the exception to
                # detect this error
                try:
                    df[column] = df[column].astype(schema_type)
                except ValueError:
                    prev_vers = (df['sqvers'][0] if not df['sqvers'].empty
                                 else None)
                    raise SqVersConversionError(
                        f'Unable to perform auto conversion of {column} '
                        f'to {schema_type} while converting schema version of '
                        f'{table} from {prev_vers} to {schema.version}.')
    df['sqvers'] = schema.version

    # We would like to return only what is in the current schema, dropping all
    # the old columns
    return df[columns_in_schema]


def _convert_bgp_vers_1_to_2(df: pd.DataFrame, **_) -> pd.DataFrame:
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
