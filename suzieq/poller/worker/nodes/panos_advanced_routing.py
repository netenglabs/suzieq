"""PAN-OS Advanced Routing Engine (ARE) support helpers.

Firewalls with ``advanced-routing: on`` reject the legacy
``<show><routing>...`` op commands with ``Command deprecated``. The ARE
equivalents return FRR-like JSON wrapped in ``<result><json>``.

The functions here convert ARE output into the legacy XML-derived structure
(``response/result/entry``) already understood by the panos normalization
templates in ``bgp.yml`` / ``routes.yml`` and by the ``_clean_panos_data``
cleaners, so no template duplication is needed. Logical routers map to VRFs.
"""
import re
from typing import Dict, List
from xml.sax.saxutils import escape

LEG_ROUTE = '<show><routing><route/></routing></show>'
LEG_BGP_SUMMARY = \
    '<show><routing><protocol><bgp><summary/></bgp></protocol></routing></show>'
LEG_BGP_PEER_GROUP = \
    '<show><routing><protocol><bgp><peer-group/></bgp></protocol></routing>' \
    '</show>'
LEG_BGP_PEER = \
    '<show><routing><protocol><bgp><peer/></bgp></protocol></routing></show>'
LEG_BFD_SUMMARY = '<show><routing><bfd><summary/></bfd></routing></show>'

AR_ROUTE = '<show><advanced-routing><route/></advanced-routing></show>'
AR_BGP_SUMMARY = \
    '<show><advanced-routing><bgp><summary/></bgp></advanced-routing></show>'
AR_BFD_SUMMARY = \
    '<show><advanced-routing><bfd><summary/></bfd></advanced-routing></show>'

# Legacy commands whose ARE output is XML with the same shape as legacy
AR_PLAIN_COMMANDS = {LEG_BFD_SUMMARY: AR_BFD_SUMMARY}

_PROTO_FLAGS = {'bgp': 'B', 'ospf': 'O', 'ospfv3': 'O', 'rip': 'R',
                'connected': 'C', 'local': 'H', 'static': 'S'}
_AGE_UNITS = {'w': 604800, 'd': 86400, 'h': 3600, 'm': 60, 's': 1}


def ar_bgp_peer_cmd(logical_router: str) -> str:
    """ARE command returning the BGP peer details of one logical router"""
    return ('<show><advanced-routing><bgp><peer><detail><logical-router>'
            f'{escape(logical_router)}</logical-router></detail></peer></bgp>'
            '</advanced-routing></show>')


def ar_age(value) -> int:
    """Convert ARE uptime strings ('51w3d23h', '01:02:03', '42') in seconds"""
    value = str(value or '').strip()
    if value.isdigit():
        return int(value)
    match = re.fullmatch(r'(\d+):(\d+):(\d+)', value)
    if match:
        hours, mins, secs = map(int, match.groups())
        return hours * 3600 + mins * 60 + secs
    return sum(int(n) * _AGE_UNITS[u]
               for n, u in re.findall(r'(\d+)([wdhms])', value))


def _wrap(entries: List[Dict]) -> Dict:
    return {'response': {'@status': 'success', 'result': {'entry': entries}}}


def _afi_safi(afkey: str) -> str:
    """'ipv4Unicast' -> 'bgpAfiIpv4-unicast' (legacy afi-safi format)"""
    match = re.match(r'(ipv4|ipv6|l2vpn)(\w+)', afkey or '')
    if not match:
        return ''
    return f'bgpAfi{match.group(1).capitalize()}-{match.group(2).lower()}'


def ar_routes(data: Dict) -> Dict:
    """Convert ``show advanced-routing route`` JSON in legacy route entries.

    Args:
        data: {logical-router: {prefix: [route, ...]}}

    Returns:
        Dict: legacy-like response, one entry per nexthop
    """
    entries = []
    for lrouter, prefixes in (data or {}).items():
        for prefix, routes in (prefixes or {}).items():
            for route in routes or []:
                nexthops = route.get('nexthops') or [{}]
                flags = (('A' if route.get('selected') else '') +
                         _PROTO_FLAGS.get(route.get('protocol'), '') +
                         ('E' if len(nexthops) > 1 else ''))
                for nhop in nexthops:
                    entries.append({
                        'virtual-router': lrouter,
                        'destination': route.get('prefix') or prefix,
                        'nexthop': nhop.get('ip') or '0.0.0.0',
                        'interface': nhop.get('interfaceName'),
                        'flags': flags,
                        'age': str(ar_age(route.get('uptime'))),
                        'metric': str(route.get('distance', 0)),
                    })
    return _wrap(entries)


def ar_bgp_summary(data: Dict) -> Dict:
    """Convert ``show advanced-routing bgp summary`` JSON (one entry per LR)
    """
    return _wrap([{'@vr': lrouter,
                   'router-id': info.get('router-id', ''),
                   'local-as': str(info.get('local-as', 0))}
                  for lrouter, info in (data or {}).items()])


def ar_bgp_peer_groups(peers_by_lr: Dict) -> Dict:
    """Derive legacy peer-group soft-reset entries from ARE peer details"""
    groups = {}
    for peers in (peers_by_lr or {}).values():
        for peer in (peers or {}).values():
            detail = peer.get('detail') or {}
            group = peer.get('peer-group-name') or detail.get('peerGroup')
            if not group:
                continue
            afis = (detail.get('addressFamilyInfo') or {}).values()
            soft = any(a.get('inboundSoftConfigPermit') for a in afis)
            groups[group] = groups.get(group) or soft
    return _wrap([{'@peer-group': g, 'soft-reset-support': 'yes' if s else 'no'}
                  for g, s in groups.items()])


def ar_bgp_peers(peers_by_lr: Dict) -> Dict:
    """Convert ARE BGP peer details in legacy peer entries, one per peer.

    Args:
        peers_by_lr: {logical-router: {peer-name: peer-detail}}

    Returns:
        Dict: legacy-like response
    """
    entries = []
    for lrouter, peers in (peers_by_lr or {}).items():
        for name, peer in (peers or {}).items():
            detail = peer.get('detail') or {}
            stats = detail.get('messageStats') or {}
            state = peer.get('state') or detail.get('bgpState', '')
            if state == 'Established' and \
                    detail.get('bgpTimerUpMsec') is not None:
                duration = int(detail['bgpTimerUpMsec']) // 1000
            else:
                duration = ar_age(peer.get('status-time'))
            hops = detail.get('externalBgpNbrMaxHopsAway') or \
                (1 if detail.get('nbrExternalLink') else 255)
            # only the AFIs enabled on the peer (ipv4/ipv6 flags)
            afis = {k: v for k, v in
                    (detail.get('addressFamilyInfo') or {}).items()
                    if peer.get(k[:4], True)} or {'': {}}
            first = next(iter(afis.values()))
            counters = [{
                '@afi-safi': _afi_safi(afkey),
                'incoming-total': str(afi.get('acceptedPrefixCounter', 0)),
                'incoming-rejected': '0',
                'outgoing-total': str(afi.get('sentPrefixCounter', 0)),
            } for afkey, afi in afis.items()]
            afi = first
            entries.append({
                '@vr': lrouter,
                '@peer': peer.get('peer-name') or name,
                'peer-group': (peer.get('peer-group-name') or
                               detail.get('peerGroup') or ''),
                'peer-address': str(peer.get('peer-ip') or
                                    detail.get('hostForeign') or ''),
                'peer-router-id': detail.get('remoteRouterId', ''),
                'remote-as': str(peer.get('remote-as') or
                                 detail.get('remoteAs') or 0),
                'status': state,
                'status-duration': str(duration),
                'multi-hop-ttl': str(hops),
                'keepalive': str(int(detail.get(
                    'bgpTimerKeepAliveIntervalMsecs', 0)) // 1000),
                'holdtime': str(int(detail.get(
                    'bgpTimerHoldTimeMsecs', 0)) // 1000),
                'reflector-client': ('client'
                                     if afi.get('routeReflectorClient')
                                     else 'not-client'),
                'local-address': str(peer.get('local-ip') or
                                     detail.get('hostLocal') or ''),
                'msg-update-in': str(stats.get('updatesRecv', 0)),
                'msg-update-out': str(stats.get('updatesSent', 0)),
                'nexthop-self': ('yes' if afi.get('routerAlwaysNextHop')
                                 else 'no'),
                'status-flap-counts': str(
                    detail.get('connectionsDropped', 0)),
                'prefix-limit': str(afi.get('prefixAllowedMax', 0)),
                # xmltodict format: dict for one entry, else a list
                'prefix-counter': {'entry': counters[0]
                                   if len(counters) == 1 else counters},
                'last-error': detail.get('lastResetDueTo', ''),
            })
    return _wrap(entries)
