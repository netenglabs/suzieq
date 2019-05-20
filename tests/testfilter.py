from copy import deepcopy

import six
import pyarrow.parquet as pa
import pandas as pd


def build_pa_filters(start_tm: str, end_tm: str,
                     key_fields: list, **kwargs):
    '''Build filters for predicate pushdown of parquet read'''

    # The time filters first
    timeset = []
    if start_tm and not end_tm:
        timeset = pd.date_range(pd.to_datetime(
            start_tm, infer_datetime_format=True), periods=2,
                                freq='15min')
        filters = [[('timestamp', '>=', timeset[0].timestamp()*1000)]]
    elif end_tm and not start_tm:
        timeset = pd.date_range(pd.to_datetime(
            end_tm, infer_datetime_format=True), periods=2,
                                freq='15min')
        filters = [[('timestamp', '<=', timeset[-1].timestamp()*1000)]]
    elif start_tm and end_tm:
        timeset = [pd.to_datetime(start_tm, infer_datetime_format=True),
                   pd.to_datetime(end_tm, infer_datetime_format=True)]
        filters = [[('timestamp', '>=', timeset[0].timestamp()*1000),
                    ('timestamp', '<=', timeset[-1].timestamp()*1000)]]
    else:
        filters = []

    # pyarrow's filters are in Disjunctive Normative Form and so filters
    # can get a bit long when lists are present in the kwargs

    for k, v in kwargs.items():
        if v and k in key_fields:
            if isinstance(v, list):
                kwdor = []
                for e in v:
                    if not filters:
                        kwdor.append([tuple(('{}'.format(k), '==',
                                             '{}'.format(e)))])
                    else:
                        if len(filters) == 1 and not isinstance(filters[0], list):
                            foo = deepcopy(filters)
                            foo.append(tuple(('{}'.format(k), '==',
                                              '{}'.format(e))))
                            kwdor.append(foo)
                        else:
                            for entry in filters:
                                foo = deepcopy(entry)
                                foo.append(tuple(('{}'.format(k), '==',
                                                  '{}'.format(e))))
                                kwdor.append(foo)

                filters = kwdor
            else:
                if not filters:
                    filters.append(tuple(('{}'.format(k), '==',
                                          '{}'.format(v))))
                else:
                    for entry in filters:
                        entry.append(tuple(('{}'.format(k), '==',
                                            '{}'.format(v))))

    return filters


def _check_contains_null(val):
    if isinstance(val, six.binary_type):
        for byte in val:
            if isinstance(byte, six.binary_type):
                compare_to = chr(0)
            else:
                compare_to = 0
            if byte == compare_to:
                return True
    elif isinstance(val, six.text_type):
        return u'\x00' in val
    return False


def check_filters(filters):
    """
    Check if filters are well-formed. This is copied from parquet.py in pyarrow
    """
    if filters is not None:
        if len(filters) == 0 or any(len(f) == 0 for f in filters):
            raise ValueError("Malformed filters")
        if isinstance(filters[0][0], six.string_types):
            # We have encountered the situation where we have one nesting level
            # too few:
            #   We have [(,,), ..] instead of [[(,,), ..]]
            filters = [filters]
        for conjunction in filters:
            for col, op, val in conjunction:
                if (
                    isinstance(val, list)
                    and all(_check_contains_null(v) for v in val)
                    or _check_contains_null(val)
                ):
                    raise NotImplementedError(
                        "Null-terminated binary strings are not supported as"
                        " filter values."
                    )
    return filters

if __name__ == '__main__':

    key_fields = ['datacenter', 'hostname', 'ifname']
    dcs = [['ospf'], ['ospf', 'evpn']]
    hosts = [['leaf01'], ['leaf01', 'leaf02']]
    ifnames = [['swp1'], ['swp1', 'swp2', 'swp3']]

    for dc in dcs:
        for host in hosts:
            for ifn in ifnames:
                filters = build_pa_filters('', '', key_fields, datacenter=dc,
                                           hostname=host, ifname=ifn)
                check_filters(filters)
                print(filters)

                filters = build_pa_filters('2019-05-02 01:28:14', '',
                                           key_fields, datacenter=dc,
                                           hostname=host, ifname=ifn)
                check_filters(filters)
                print(filters)

                filters = build_pa_filters('', '2019-05-02 01:28:14',
                                           key_fields, datacenter=dc,
                                           hostname=host, ifname=ifn)
                check_filters(filters)
                print(filters)

                filters = build_pa_filters('2019-05-02 01:28:14', '05/02/19 02:10:10',
                                           key_fields, datacenter=dc,
                                           hostname=host, ifname=ifn)
                check_filters(filters)
                print(filters)

    
