"""Tests for PAN-OS Advanced Routing conversion and Panorama proxy mode"""
import json
from unittest.mock import MagicMock

import pytest

from suzieq.poller.worker.nodes import panos_advanced_routing as ar
from suzieq.poller.worker.nodes.node import PanosNode

AR_ROUTES = {
    'LR-1': {
        '0.0.0.0/0': [{
            'prefix': '0.0.0.0/0', 'protocol': 'bgp', 'selected': True,
            'installed': True, 'distance': 20, 'uptime': '1w2d03h',
            'nexthops': [
                {'ip': '192.0.2.1', 'interfaceName': 'ethernet1/1'},
                {'ip': '192.0.2.5', 'interfaceName': 'ethernet1/2'}]}],
        '198.51.100.0/24': [{
            'prefix': '198.51.100.0/24', 'protocol': 'connected',
            'selected': True, 'distance': 0, 'uptime': '01:02:03',
            'nexthops': [{'directlyConnected': True,
                          'interfaceName': 'ethernet1/3'}]}],
    }
}

AR_BGP_SUMMARY = {'LR-1': {'router-id': '203.0.113.1', 'local-as': 65001}}

AR_PEERS = {
    'LR-1': {
        'PEER-A': {
            'peer-ip': '192.0.2.1', 'remote-as': 65002, 'state': 'Established',
            'peer-group-name': 'GRP-A', 'local-ip': '192.0.2.2',
            'detail': {
                'remoteRouterId': '203.0.113.2', 'bgpTimerUpMsec': 3600000,
                'bgpTimerKeepAliveIntervalMsecs': 10000,
                'bgpTimerHoldTimeMsecs': 30000, 'nbrExternalLink': True,
                'connectionsDropped': 2,
                'messageStats': {'updatesRecv': 7, 'updatesSent': 3},
                'addressFamilyInfo': {'ipv4Unicast': {
                    'acceptedPrefixCounter': 12, 'sentPrefixCounter': 4,
                    'inboundSoftConfigPermit': True}}}},
        'PEER-B': {
            'peer-ip': '192.0.2.9', 'remote-as': 65003, 'state': 'Active',
            'status-time': '2d01h', 'detail': {}},
    }
}


def test_ar_age():
    """uptime formats"""
    assert ar.ar_age('1w2d03h') == 604800 + 2 * 86400 + 3 * 3600
    assert ar.ar_age('01:02:03') == 3723
    assert ar.ar_age('42') == 42
    assert ar.ar_age(None) == 0


def test_ar_routes():
    """one legacy entry per nexthop, LR becomes the VRF"""
    entries = ar.ar_routes(AR_ROUTES)['response']['result']['entry']
    assert len(entries) == 3
    bgp = [e for e in entries if e['destination'] == '0.0.0.0/0']
    assert {e['nexthop'] for e in bgp} == {'192.0.2.1', '192.0.2.5'}
    assert all(e['flags'] == 'ABE' and e['virtual-router'] == 'LR-1'
               for e in bgp)
    conn = [e for e in entries if e['destination'] == '198.51.100.0/24'][0]
    assert conn['flags'] == 'AC'
    assert conn['nexthop'] == '0.0.0.0'
    assert conn['interface'] == 'ethernet1/3'
    assert conn['age'] == '3723'


def test_ar_bgp():
    """summary, peer groups and peers"""
    summ = ar.ar_bgp_summary(AR_BGP_SUMMARY)['response']['result']['entry']
    assert summ == [{'@vr': 'LR-1', 'router-id': '203.0.113.1',
                     'local-as': '65001'}]
    groups = ar.ar_bgp_peer_groups(AR_PEERS)['response']['result']['entry']
    assert groups == [{'@peer-group': 'GRP-A', 'soft-reset-support': 'yes'}]
    peers = {p['@peer']: p for p in
             ar.ar_bgp_peers(AR_PEERS)['response']['result']['entry']}
    peer = peers['PEER-A']
    assert peer['@vr'] == 'LR-1'
    assert peer['status'] == 'Established'
    assert peer['status-duration'] == '3600'
    assert peer['remote-as'] == '65002'
    assert peer['multi-hop-ttl'] == '1'
    assert (peer['keepalive'], peer['holdtime']) == ('10', '30')
    assert peer['prefix-counter']['entry'] == {
        '@afi-safi': 'bgpAfiIpv4-unicast', 'incoming-total': '12',
        'incoming-rejected': '0', 'outgoing-total': '4'}
    assert len(peers) == 2
    assert peers['PEER-B']['status'] == 'Active'
    assert peers['PEER-B']['status-duration'] == str(2 * 86400 + 3600)


def _xml_json(data) -> str:
    return ('<response status="success"><result><json>'
            f'{json.dumps(data)}</json></result></response>')


def _node(advanced: bool) -> PanosNode:
    node = PanosNode()
    node.api_key = 'KEY'
    node.serial = '0123456789'
    node._advanced_routing = advanced  # pylint: disable=protected-access
    return node


async def test_panorama_ar_commands():
    """AR firewall: legacy commands replaced, target set, key not in URL"""
    calls = []
    answers = {
        ar.AR_ROUTE: _xml_json(AR_ROUTES),
        ar.AR_BGP_SUMMARY: _xml_json(AR_BGP_SUMMARY),
        ar.ar_bgp_peer_cmd('LR-1'): _xml_json(AR_PEERS['LR-1']),
        ar.AR_BFD_SUMMARY: '<response status="success"><result/></response>',
    }

    class Resp:
        """fake aiohttp response"""
        status = 200

        def __init__(self, text):
            self._text = text

        async def text(self):
            """body"""
            return self._text

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    def post(url, data, timeout):  # pylint: disable=unused-argument
        calls.append((url, data))
        return Resp(answers[data['cmd']])

    node = _node(True)
    node.address, node.port = 'panorama.example', 443
    node._conn = MagicMock()  # pylint: disable=protected-access
    node._conn.post = post  # pylint: disable=protected-access

    async def run():
        cache = {}
        out = {}
        for cmd in (ar.LEG_ROUTE, ar.LEG_BGP_SUMMARY, ar.LEG_BGP_PEER,
                    ar.LEG_BGP_PEER_GROUP, ar.LEG_BFD_SUMMARY):
            out[cmd] = await node._panos_exec(  # pylint: disable=protected-access
                cmd, 10, cache)
        return out

    out = await run()
    assert all(status == 200 for status, _ in out.values())
    routes = json.loads(out[ar.LEG_ROUTE][1])
    assert len(routes['response']['result']['entry']) == 3
    # peer details fetched once for both peer and peer-group commands
    assert [d['cmd'] for _, d in calls].count(
        ar.ar_bgp_peer_cmd('LR-1')) == 1
    assert all(d['target'] == '0123456789' and d['key'] == 'KEY'
               and 'KEY' not in url for url, d in calls)
    assert not any('<routing>' in d['cmd'] for _, d in calls)


@pytest.mark.parametrize('flag,expected', [('on', True), ('off', False)])
async def test_advanced_routing_detection(flag, expected):
    """advanced-routing flag from show system info"""
    node = _node(False)
    node.logger = MagicMock()
    data = ('hostname: fw-1\nuptime: 1 days, 01:02:03\n'
            f'sw-version: 11.1.6\nadvanced-routing: {flag}\n')
    output = [{'status': 0, 'data': data, 'cmd_timestamp': 1700000000000}]
    await node._parse_init_dev_data_devtype(  # pylint: disable=W0212
        output, None)
    assert node.hostname == 'fw-1'
    assert node._advanced_routing is expected  # pylint: disable=W0212
