from typing import Dict, List, Optional, Set, Tuple

from nubia.internal import context

from suzieq.shared.context import SqContext
from suzieq.shared.utils import lru_cache, timed_lru_cache
from suzieq.sqobjects import get_sqobject, get_tables

virt_tbl_cmd_mapping: Dict[str, str] = {
    'endpoint': 'device',
    'path': 'device',
    'topology': 'device',
    'namespace': 'device',
    'route': 'routes',
    'mac': 'macs',
    'interface': 'interfaces',
}


@timed_lru_cache(60)
def completion_get_data(cmd: str, column: str,
                        **kwargs) -> Set[str]:
    '''Caching enabled dataframe retrieval'''

    result = set()
    nubia_ctxt = context.get_context()
    if not nubia_ctxt:
        return result

    ctxt: SqContext = nubia_ctxt.ctxt

    # kwargs are passed with values as tuples, not lists which
    # causes a bunch of problems in asserts. So, convert tuples
    # to lists again
    for k, v in kwargs.items():
        if isinstance(v, tuple):
            kwargs[k] = list(v)

    if cmd == "extdb":
        result = set()
        # TODO: implement autocompletion with external tables
        # ext_table = kwargs.pop('ext_table', None)
        # return get_sqobject(cmd)(ext_table=ext_table, context=ctxt)
    else:
        df = get_sqobject(cmd)(context=ctxt).unique(columns=[column], **kwargs)
        if not df.empty and 'error'not in df.columns:
            result = set(df[column])

    return result


@lru_cache
def completion_get_columns(cmd: str, component: Optional[str] = None,
                           ) -> List[str]:
    '''Return columns associated with a table for unique/top/assert'''
    ctxt: SqContext = context.get_context().ctxt
    sqobj = None

    if cmd == 'sqlog' and component:
        sqobj = get_sqobject(cmd)(component=component, context=ctxt)
    elif cmd != 'sqlog':
        sqobj = get_sqobject(cmd)(context=ctxt)
    if sqobj and sqobj.schema:
        return sorted(sqobj.schema.get_user_visible_fields())
    return []


def get_kwargs_so_far(raw_cmd: str, keywords:  List[str]) -> Dict:
    '''Parse the raw_cmd and return kwargs for requested keywords'''

    kwargs: Dict[str, Tuple] = {}
    for keyword in keywords:
        kwargs[keyword] = tuple()
        if f' {keyword}=' in raw_cmd:
            val_str = raw_cmd.split(f' {keyword}=')[-1]
            if val_str:
                kwargs[keyword] = tuple([val_str.split()[0]])

    return kwargs


def return_completions(cmd, column, val_so_far, quote_result=False,
                       **kwargs) -> List[str]:
    '''Given a cmd and column, return valid completion list'''

    try:
        valid_set = completion_get_data(cmd, column, **kwargs)
    except Exception:
        valid_set = []

    if val_so_far:
        result = sorted(
            [x for x in valid_set if str(x).startswith(val_so_far)])
    else:
        result = sorted(list(valid_set))

    if quote_result:
        result = [f'"{x}"' for x in result]

    return result


def namespace_completer(_cmd: str, _: str, last_token: str,
                        _raw_cmd: str) -> List[str]:
    '''Provide dynamic completion list for namespace'''

    ns_so_far: Optional[str] = None

    if isinstance(last_token, str):
        ns_so_far = last_token.split('=')[-1]

    return return_completions('device', 'namespace', ns_so_far,
                              ignore_neverpoll=True)


def vrf_completer(cmd: str, _subcmd: str, last_token: str,
                  raw_cmd: str) -> List[str]:
    '''Dynamic completion of hostname'''

    vrf_so_far = None

    if isinstance(last_token, str):
        vrf_so_far = last_token.split('=')[-1]

    kwargs = get_kwargs_so_far(raw_cmd, ['namespace', 'hostname'])

    if cmd in ['path', 'topology', 'endpoint']:
        cmd = 'address'

    return return_completions(cmd, 'vrf', vrf_so_far, **kwargs)


def hostname_completer(cmd: str, _subcmd: str, last_token: str,
                       raw_cmd: str) -> List[str]:
    '''Dynamic completion of hostname'''

    hostname_so_far: Optional[str] = None

    if isinstance(last_token, str):
        hostname_so_far = last_token.split('=')[-1]

    kwargs = get_kwargs_so_far(raw_cmd, ['namespace'])

    return return_completions('device', 'hostname', hostname_so_far, **kwargs)


def column_name_completer(cmd: str, subcmd: str, last_token: str,
                          raw_cmd: str) -> List[str]:
    '''Return completions for column name'''
    col_so_far = None

    if isinstance(last_token, str):
        col_so_far = last_token.split('=')[-1]

    if cmd == "sqlog":
        component = get_kwargs_so_far(raw_cmd, ['component'])
        kwargs = {
            'component': (component.get('component', [None]) or
                          [None])[0]
        }
    else:
        kwargs = {}

    if (subcmd in ['unique', 'top', 'assert']
            and cmd not in ["endpoint", "assert"]):
        fields = completion_get_columns(cmd, **kwargs)
    else:
        fields = []

    if fields:
        if col_so_far:
            return sorted([f for f in fields if f.startswith(col_so_far)])

    return sorted(fields)


def route_proto_completer(cmd: str, _subcmd: str, last_token: str,
                          raw_cmd: str) -> List[str]:
    '''Dynamic completion of protocol field in routing table'''

    if isinstance(last_token, str):
        proto_so_far = last_token.split('=')[-1]
    else:
        proto_so_far = ''

    kwargs = get_kwargs_so_far(raw_cmd, ['namespace', 'hostname'])

    return return_completions(cmd, 'protocol', proto_so_far, **kwargs)


def service_completer(_cmd: str, _subcmd: str, last_token: str,
                      _raw_cmd: str) -> List[str]:
    '''Dynamic completion of service names in sqpoller table'''

    svc_so_far = None

    if isinstance(last_token, str):
        svc_so_far = last_token.split('=')[-1]

    svcs = set({x for x in get_tables()
                if x not in ['path', 'topology', 'namespace', 'endpoint',
                             'topcpu', 'topmem',
                             'extdb']})
    if svcs:
        if svc_so_far:
            return sorted([x for x in svcs if x.startswith(svc_so_far)])
        else:
            return sorted(svcs)

    return []


def query_completer(_cmd: str, _subcmd: str, last_token: str,
                    _raw_cmd: str) -> List[str]:
    '''Dynamic completion of service names in sqpoller table'''

    q_so_far = None

    if isinstance(last_token, str):
        q_so_far = last_token.split('=')[-1]

    queries = [x for x in completion_get_data('query', 'name')
               if x]
    if queries:
        if q_so_far:
            return sorted([x for x in queries if x.startswith(q_so_far)])
        else:
            return sorted(queries)

    return []


def vlan_completer(cmd: str, _subcmd: str, last_token: str,
                   raw_cmd: str) -> List[str]:
    '''Dynamic completion of VLAN'''

    vlan_so_far = None

    if isinstance(last_token, str):
        vlan_so_far = last_token.split('=')[-1]

    kwargs = get_kwargs_so_far(raw_cmd, ['namespace'])

    return return_completions(cmd, 'vlan', vlan_so_far, **kwargs)


def vni_completer(cmd: str, _subcmd: str, last_token: str,
                  raw_cmd: str) -> List[str]:
    '''Dynamic completion of VLAN'''

    vni_so_far = None

    if isinstance(last_token, str):
        vni_so_far = last_token.split('=')[-1]

    kwargs = get_kwargs_so_far(raw_cmd, ['namespace'])

    return return_completions(cmd, 'vni', vni_so_far, **kwargs)


def bridgeid_completer(cmd: str, _subcmd: str, last_token: str,
                       raw_cmd: str) -> List[str]:
    '''Dynamic completion of STP bridgeId'''

    bridge_id_so_far = None

    if isinstance(last_token, str):
        bridge_id_so_far = last_token.split('=')[-1]

    kwargs = get_kwargs_so_far(raw_cmd, ['namespace'])

    return return_completions(cmd, 'bridgeId', bridge_id_so_far, **kwargs)


def stp_vlan_completer(cmd: str, _subcmd: str, last_token: str,
                       raw_cmd: str) -> List[str]:
    '''Dynamic completion of STP VLANID for PVST+'''

    vlan_so_far = None

    if isinstance(last_token, str):
        vlan_so_far = last_token.split('=')[-1]

    kwargs = get_kwargs_so_far(raw_cmd, ['namespace'])

    return return_completions(cmd, 'instanceId', vlan_so_far, **kwargs)


def instanceId_completer(cmd: str, _subcmd: str, last_token: str,
                         raw_cmd: str) -> List[str]:
    '''Dynamic completion of STP instanceId'''

    instance_id_so_far = None

    if isinstance(last_token, str):
        instance_id_so_far = last_token.split('=')[-1]

    kwargs = get_kwargs_so_far(raw_cmd, ['namespace'])

    return return_completions(cmd, 'instanceId', instance_id_so_far, **kwargs)


def inv_type_completer(cmd: str, _subcmd: str, last_token: str,
                       raw_cmd: str) -> List[str]:
    '''Dynamic completion of inventory type'''

    inv_type_so_far = None

    if isinstance(last_token, str):
        inv_type_so_far = last_token.split('=')[-1]

    kwargs = get_kwargs_so_far(raw_cmd, ['namespace'])

    return return_completions(cmd, 'type', inv_type_so_far, **kwargs)


def license_name_completer(cmd: str, _subcmd: str, last_token: str,
                           raw_cmd: str) -> List[str]:
    '''Dynamic completion of device license name'''

    lic_so_far = None

    if isinstance(last_token, str):
        lic_so_far = last_token.split('=')[-1]

    kwargs = get_kwargs_so_far(raw_cmd, ['namespace'])

    return return_completions(cmd, 'name', lic_so_far, quote_result=True,
                              **kwargs)
