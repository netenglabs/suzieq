import os
import shutil
import signal
import sys
import yaml
from subprocess import check_output, CalledProcessError, Popen, PIPE
from tempfile import mkstemp
from collections import Counter
import time
import pytest
from _pytest.mark.structures import Mark, MarkDecorator
from suzieq.cli.sqcmds import *
from tests import conftest

# This is not just a set of tests, it will also update
#  the data collected for other test_sqcmds tests

ansible_file = '/.vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory'


def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


def create_config(t_dir, suzieq_dir):
    # We need to create a tempfile to hold the config
    tmpconfig = conftest._create_context_config()
    tmpconfig['data-directory'] = f"{t_dir}/parquet-out"
    tmpconfig['service-directory'] = f"{suzieq_dir}/{tmpconfig['service-directory']}"
    tmpconfig['schema-directory'] = f"{suzieq_dir}/{tmpconfig['schema-directory']}"

    fname = 'suzieq-cfg.yml'

    with open(fname, 'w') as f:
        f.write(yaml.dump(tmpconfig))
    return fname


def _run_cmd(cmd):
    output = None
    error = None
    returncode = None
    try:
        output = check_output(cmd)
    except CalledProcessError as e:
        error = e.output
        returncode = e.returncode
        print(f"ERROR: {e.output} {e.returncode}")

    if output:
        output = output.decode('utf-8')

    return output, returncode


def _get_cndcn(path):
    os.chdir(path)
    _run_cmd(['git', 'clone',
              'https://github.com/ddutt/cloud-native-data-center-networking.git'])
    return os.getcwd() + '/cloud-native-data-center-networking'


def run_sqpoller(name, ansible_dir, suzieq_dir):
    sqcmd_path = [sys.executable, f"{suzieq_dir}/suzieq/poller/sq-poller"]
    sqcmd = sqcmd_path + ['-i', ansible_dir + ansible_file, '-n', name]

    pid = Popen(sqcmd).pid
    time.sleep(180)
    os.kill(pid, signal.SIGSTOP)


def run_scenario(scenario):
    _run_cmd(['sudo', 'ansible-playbook', '-b', '-e', f'scenario={scenario}',
              'deploy.yml'])
    time.sleep(15)
    out, code = _run_cmd(['sudo', 'ansible-playbook', 'ping.yml'])

    return out, code


def check_suzieq_data(suzieq_dir, name):
    sqcmd_path = [sys.executable, f"{suzieq_dir}/{conftest.suzieq_cli_path}"]
    sqcmd = sqcmd_path + ['device', 'unique', '--columns=namespace',
                          f'--namespace={name}']
    out, ret = _run_cmd(sqcmd)
    assert '14' in out  # there should be 14 different hosts collected
    for cmd in ['bgp', 'interface', 'ospf', 'evpnVni']:
        sqcmd = sqcmd_path + [cmd, 'assert', f'--namespace={name}']
        out, ret = _run_cmd(sqcmd)
        assert ret is None or ret is 1 or ret is 255


def collect_data(topology, proto, scenario, name, suzieq_dir):
    os.chdir(f"{topology}/{proto}")
    _vagrant_up()
    out, code = run_scenario(scenario)
    if code is not None:
        print("retrying setting up scenario")
        _vagrant_down()
        run_scenario(scenario)
    dir = os.getcwd() + '/..'
    cfg_file = create_config('../', suzieq_dir)
    print(f"config file {os.getcwd()}/{cfg_file}")
    run_sqpoller(name, dir, suzieq_dir)
    check_suzieq_data(suzieq_dir, name)
    _vagrant_down()
    os.chdir('../..')


def _vagrant_up():
    print(os.getcwd())
    _run_cmd(['sudo', 'vagrant', 'up'])
    out, ret = _run_cmd(['sudo', 'vagrant', 'status'])
    _run_cmd(['sudo', 'chown', '-R', os.environ['USER'], '..'])
    return ret


def _vagrant_down():
    print("VAGRANT DOWN")
    _run_cmd(['sudo', 'vagrant', 'destroy', '-f'])


@pytest.fixture
def _vagrant_setup():
    yield
    _vagrant_down()


class TestUpdate:
    @pytest.mark.update_data
    @pytest.mark.skipif(not os.environ.get('UPDATE_SQCMDS', None),
                        reason='Not updating data')
    def test_update_data(self, tmp_path, _vagrant_setup):
        orig_dir = os.getcwd()
        path = _get_cndcn(tmp_path)
        os.chdir(path + '/topologies')

        #collect_data('dual-attach', 'evpn', 'ospf-ibgp', 'ospf-ibgp', orig_dir)
        collect_data('dual-attach', 'evpn', 'centralized', 'dual-evpn', orig_dir)
        #collect_data('single-attach', 'ospf', 'numbered', 'ospf-single', orig_dir)

        dst_dir = f'{orig_dir}/tests/data/multidc'
        shutil.rmtree(dst_dir)
        copytree('/dual-attach/parquet-out', dst_dir)
        copytree('/single-attach/parquet-out', dst_dir)
        shutil.rmtree('/dual-attach/parquet-out')
        shutil.rmtree('/single-attach/parquet-out')

        dst_dir = f'{orig_dir}/tests/data/basic_dual_bgp'
        shutil.rmtree(dst_dir)
        #collect_data('dual-attach', 'bgp', 'numbered', 'dual-bgp', orig_dir)
        #copytree('/dual-attach/parquet-out', dst_dir)

# TODO
# run update commands and see the differences
# how to change test_sqcmds to be more resilient
# have vagrant only go up/down when changing single/dual ?

tests = [
    ['bgp', 'numbered'],
    #['bgp', 'unnumbered'],
    #['bgp', 'docker']
]
class TestDualAttach:
    @pytest.mark.dual_attach
    @pytest.mark.skipif(not os.environ.get('SUZIEQ_POLLER', None),
                        reason='Not updating data')
    @pytest.mark.parametrize("proto, scenario", tests)
    def test_data(self, proto, scenario):
        orig_dir = os.getcwd()
        path = _get_cndcn(tmp_path)
        os.chdir(path + '/topologies')
        name = f'dual-attach_{proto}_{scenario}'
        collect_data('dual-attach', proto, scenario, name, orig_dir)
        # TODO
        #  run the tests


class TestSingleAttach:
    pass