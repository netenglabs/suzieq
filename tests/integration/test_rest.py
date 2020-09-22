import pytest
import os, shlex
from subprocess import check_output, CalledProcessError
import requests

from tests.conftest import cli_commands, tables, setup_sqcmds

# TODO
# launch uvicorn for localhost and test against it
# figure out how to make localhost work, instead of a specific IP

ENDPOINT = "http://192.168.1.185:8000/api/v1"

 # these service/verb pairs should return errors
bad_verbs = {'address/assert': 404, 'address/lpm': 404,
             'arpnd/assert': 404, 'arpnd/lpm': 404,
             'bgp/lpm': 404,
             'device/assert': 404, 'device/lpm': 404,
             'evpnVni/lpm': 404,
             'interface/lpm': 404,
             'lldp/assert': 404, 'lldp/lpm': 404,               
             'mac/assert': 404, 'mac/lpm': 404,
             'mlag/assert': 404, 'mlag/lpm': 404,
             'ospf/lpm': 404,
             'path/lpm': 404,
             'route/assert': 404, 
             'vlan/assert': 404, 'vlan/lpm': 404,
            }

# these service/verb/filter tuples should return errors
bad_filters = {'lpm?hostname=leaf01':404,

               'path/show?': 404, 'path/show?hostname=leaf01': 404, 'path/show?namespace=dual-bgp': 404,
               'path/show?address=10.0.0.1': 404,
               'route/lpm?': 404, 'route/lpm?hostname=leaf01': 404, 'route/lpm?namespace=dual-bgp': 404,
               }

def get(endpoint, command, verb, args):
    url = f"{endpoint}/{command}/{verb}?{args}"
   
    ret = requests.get(url)
    #print(f"{url}: {ret.status_code}")
    if ret.status_code != 200:
        c_v = f"{command}/{verb}"
        c_v_f = f"{c_v}?{args}"
        if c_v in bad_verbs:
             assert bad_verbs[c_v] == ret.status_code
        elif c_v_f in bad_filters:
            assert bad_filters[c_v_f] == ret.status_code    
        else:
            ret.raise_for_status()

    return ret.status_code

VERBS = ['show', 'summarize', 'assert', 'lpm', 'top']
FILTERS = ['', 'hostname=leaf01', 'namespace=dual-bgp', 
            'address=10.0.0.1', 
           'dest=172.16.2.104&src=172.16.1.101&namespace=dual-evpn',
          ]

@pytest.mark.parametrize("command, verbs, args", [
    (cmd, VERBS, FILTERS) for cmd in cli_commands
])
def test_rest_commands(setup_nubia, command, verbs, args):
    for verb in verbs:
        for arg in args:
           get(ENDPOINT, command, verb, arg)
            

def test_bad_rest():
    pass

if __name__ == "__main__":
    pass