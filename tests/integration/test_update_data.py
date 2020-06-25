import os
import shlex
import glob
import shutil
import signal
import sys
import yaml
import json
from subprocess import check_output, check_call, CalledProcessError, Popen, PIPE, STDOUT
from collections import Counter
import time
import pytest
from _pytest.mark.structures import Mark, MarkDecorator
from suzieq.cli.sqcmds import *
from tests import conftest
import logging
import random

# This is not just a set of tests, it will also update
#  the data collected for other test_sqcmds tests

ansible_file = '/.vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory'
samples_dir = 'tests/integration/sqcmds/samples/'
UPDATE_SQCMDS = 'tests/utilities/update_sqcmds.py'
cndcn_samples_dir = 'tests/integration/all_cndcn/'
parquet_dir = '/tmp/suzieq-tests-parquet'


def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            if os.path.isdir(d):
                copytree(s, d, symlinks, ignore)
            else:
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


def run_cmd(cmd):
    output = None
    error = None
    returncode = None
    print(f"CMD: {cmd}")
    logging.warning(f"CMD: {cmd}")
    try:
        output = check_output(cmd, stderr=STDOUT)
    except CalledProcessError as e:
        error = e.output
        returncode = e.returncode
        logging.warning(f"ERROR: {e.output} {e.returncode}")

    if output:
        output = output.decode('utf-8')

    return output, returncode, error


def get_cndcn(path):
    os.chdir(path)
    run_cmd(['git', 'clone',
             'https://github.com/netenglabs/cloud-native-data-center-networking.git'])
    return os.getcwd() + '/cloud-native-data-center-networking'


def run_sqpoller(name, ansible_dir, suzieq_dir):
    sqcmd_path = [sys.executable, f"{suzieq_dir}/suzieq/poller/sq-poller"]
    sqcmd = sqcmd_path + ['-i', ansible_dir + ansible_file, '-n', name]

    pid = Popen(sqcmd).pid
    time.sleep(60)
    os.kill(pid, signal.SIGSTOP)


def run_scenario(scenario):
    run_cmd(['ansible-playbook', '-b', '-e', f'scenario={scenario}',
              'deploy.yml'])
    time.sleep(15)
    out, code, err = run_cmd(['ansible-playbook', 'ping.yml'])

    return out, code


def check_suzieq_data(suzieq_dir, name, threshold='14'):
    sqcmd_path = [sys.executable, f"{suzieq_dir}/{conftest.suzieq_cli_path}"]
    sqcmd = sqcmd_path + ['device', 'unique', '--columns=namespace',
                          f'--namespace={name}']
    out, ret, err = run_cmd(sqcmd)
    assert threshold in out, f'failed {out}, {err}'  # there should be 14 different hosts collected
    for cmd in ['bgp', 'interface', 'ospf', 'evpnVni']:
        sqcmd = sqcmd_path + [cmd, 'assert', f'--namespace={name}']
        out, code, err = run_cmd(sqcmd)
        assert code is None or code is 1 or code is 255


def collect_data(topology, proto, scenario, name, suzieq_dir):
    os.chdir(f"{topology}/{proto}")
    vagrant_up()
    out, code = run_scenario(scenario)
    if code is not None:
        logging.warning("retrying setting up scenario")
        vagrant_down()
        time.sleep(10)
        vagrant_up()
        run_scenario(scenario)
    dir = os.getcwd() + '/..'
    cfg_file = create_config('../', suzieq_dir)
    logging.warning(f"config file {os.getcwd()}/{cfg_file}")
    run_sqpoller(name, dir, suzieq_dir)
    check_suzieq_data(suzieq_dir, name)
    vagrant_down()
    sleep_time = random.random() * 600
    time.sleep(sleep_time)
    os.chdir('../..')
    return cfg_file


def vagrant_up():
    logging.warning(f"VAGRANT dir {os.getcwd()}")
    print(f"VAGRANT dir {os.getcwd()}")
    run_cmd(['vagrant', 'up'])
    out, code, err = run_cmd(['vagrant', 'status'])
    logging.warning(f"VAGRANT UP {out}")
    run_cmd(['vagrant', 'up'])
    out, code, err = run_cmd(['vagrant', 'status'])
    logging.warning(f"VAGRANT UP {out}")
    return code


def vagrant_down():
    logging.warning("VAGRANT DOWN")
    run_cmd(['vagrant', 'destroy', '-f'])


# this is an attempt to clean up vagrant if something goes wrong
@pytest.fixture
def vagrant_setup():
    yield
    vagrant_down()


def git_del_dir(dir):
    if os.path.isdir(dir):
        try:
            check_call(['git', 'rm', dir])
        except CalledProcessError as e:
            shutil.rmtree(dir)


def update_sqcmds(files, data_dir=None, namespace=None):
    for file in files:
        cmd = ['python3', UPDATE_SQCMDS, '-f', file, '-o']
        if data_dir:
            cmd += ['-d', data_dir]
        if namespace:
            cmd += ['-n', namespace]
        logging.warning(cmd)
        out, code, error = run_cmd(cmd)
        assert code is None or code == 0, f"{file} failed, {out} {code} {error}"


class TestUpdate:
    @pytest.mark.update_data
    @pytest.mark.skipif(not os.environ.get('SUZIEQ_POLLER', None),
                        reason='Not updating data')
    def test_update_data(self, tmp_path, vagrant_setup):
        orig_dir = os.getcwd()
        path = get_cndcn(tmp_path)
        os.chdir(path + '/topologies')

        collect_data('dual-attach', 'evpn', 'ospf-ibgp', 'ospf-ibgp', orig_dir)
        collect_data('dual-attach', 'evpn', 'centralized', 'dual-evpn', orig_dir)
        collect_data('single-attach', 'ospf', 'numbered', 'ospf-single', orig_dir)

        dst_dir = f'{orig_dir}/tests/data/multidc/parquet-out'
        git_del_dir(dst_dir)
        copytree('dual-attach/parquet-out', dst_dir)
        copytree('single-attach/parquet-out', dst_dir)
        shutil.rmtree('dual-attach/parquet-out')
        shutil.rmtree('single-attach/parquet-out')

        collect_data('dual-attach', 'bgp', 'unnumbered', 'dual-bgp', orig_dir)

        dst_dir = f'{orig_dir}/tests/data/basic_dual_bgp/parquet-out'
        if os.path.isdir(dst_dir):
            shutil.rmtree(dst_dir)

        copytree('dual-attach/parquet-out', dst_dir)
        shutil.rmtree('dual-attach/parquet-out')

        # update the samples data with updates from the newly collected data
        os.chdir(orig_dir)
        update_sqcmds(glob.glob(f'{samples_dir}/*.yml'))

# TODO
# have vagrant only go up/down when changing single/dual ?

tests = [
    ['bgp', 'numbered'],
    ['bgp', 'unnumbered'],
    ['bgp', 'docker'],
    ['ospf', 'numbered'],
    ['ospf', 'unnumbered'],
    ['ospf', 'docker'],
    ['evpn', 'centralized'],
    ['evpn', 'distributed'],
    ['evpn', 'ospf-ibgp']
]


def _test_sqcmds(testvar, context_config):
    output, error = conftest.setup_sqcmds(testvar, context_config)

    jout = []
    if output:

        try:
            jout = json.loads(output.decode('utf-8').strip())
        except json.JSONDecodeError:
            jout = output

    if 'output' in testvar:
        try:
            expected_jout = json.loads(testvar['output'].strip())
        except json.JSONDecodeError:
            expected_jout = testvar['output']

        assert (type(expected_jout) == type(jout))

        if len(expected_jout) > 0:
            assert len(jout) > 0

    elif not error and 'xfail' in testvar:
        # this was marked to fail, but it succeeded so we must return
        return
    elif error and 'xfail' in testvar and 'error' in testvar['xfail']:
        if jout.decode("utf-8") == testvar['xfail']['error']:
            assert False
        else:
            assert True
    elif 'error' in testvar and 'error' in testvar['error']:
        assert error, \
           f"expected error, but got: output: {output}, error: {error}, xfail: {xfail}"
    else:
        raise Exception(f"either xfail or output requried {error}")


def _create_data(topology, proto, scenario, path):
    orig_dir = os.getcwd()
    path = get_cndcn(path)
    os.chdir(path + '/topologies')
    name = f'{topology}_{proto}_{scenario}'

    collect_data(topology, proto, scenario, name, orig_dir)

    if not os.path.isdir(parquet_dir):
        os.mkdir(parquet_dir)
    if not os.path.isdir(f'{parquet_dir}/{name}'):
        os.mkdir(f'{parquet_dir}/{name}')

    copytree(f"{path}/topologies/{topology}/parquet-out",
             f"{parquet_dir}/{name}/parquet-out/")

    os.chdir(orig_dir)
    if os.environ.get('UPDATE_SQCMDS', None):
        update_sqcmds(glob.glob(f'{cndcn_samples_dir}/{name}/*.yml'),
                      data_dir=f"{parquet_dir}/{name}/parquet-out",
                      namespace=name)


def _test_data(topology, proto, scenario, testvar):
    name = f'{topology}_{proto}_{scenario}'
    testvar['data-directory'] = f"{parquet_dir}/{name}/parquet-out"
    _test_sqcmds(testvar, conftest._create_context_config())


# these are grouped as classes so that we will only do one a time
#  when using --dist=loadscope
# because we have two vagrant files in CNDCN, that means we can run
# two simulations at a time, one single-attach and one dual-attach

class TestDualAttach:
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("proto, scenario", tests)
    def test_create_dual_data(self, proto, scenario, tmp_path, vagrant_setup):
        _create_data('dual-attach', proto, scenario, tmp_path)

    # this needs to be run after the tests are created and updated
    #  there is no way to have pytest run the load_up_the_tests before the updater
    #  so we prevent this running if you are updating the sqcmds
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_dual_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_bgp_numbered/")))
    def test_dual_bgp_numbered_data(self, testvar):
        _test_data('dual-attach', 'bgp', 'numbered', testvar)

    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_dual_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_bgp_unnumbered/")))
    def test_dual_bgp_numbered_data(self, testvar):
        _test_data('dual-attach', 'bgp', 'unnumbered', testvar)

    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_dual_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_bgp_docker/")))
    def test_dual_bgp_numbered_data(self, testvar):
        _test_data('dual-attach', 'bgp', 'docker', testvar)

    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_dual_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_ospf_numbered/")))
    def test_dual_ospf_numbered_data(self, testvar):
        _test_data('dual-attach', 'ospf', 'numbered', testvar)

    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_dual_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_ospf_unnumbered/")))
    def test_dual_ospf_numbered_data(self, testvar):
        _test_data('dual-attach', 'ospf', 'unnumbered', testvar)

    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_dual_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_ospf_docker/")))
    def test_dual_ospf_numbered_data(self, testvar):
        _test_data('dual-attach', 'ospf', 'docker', testvar)

    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_dual_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_evpn_centralized/")))
    def test_dual_evpn_centralized_data(self, testvar):
        _test_data('dual-attach', 'evpn', 'centralized', testvar)

    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_dual_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_evpn_distributed/")))
    def test_dual_evpn_distributed_data(self, testvar):
        _test_data('dual-attach', 'evpn', 'distributed', testvar)

    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_dual_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_evpn_ospf-ibgp/")))
    def test_dual_evpn_ospf_ibgp_data(self, testvar):
        _test_data('dual-attach', 'evpn', 'ospf-ibgp', testvar)


class TestSingleAttach:
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("proto, scenario", tests)
    def test_create_single_data(self, proto, scenario, tmp_path, vagrant_setup):
        _create_data('single-attach', proto, scenario, tmp_path)

    # this needs to be run after the tests are created and updated
    #  there is no way to have pytest run the load_up_the_tests before the updater
    #  so we prevent this running if you are updating the sqcmds
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_single_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/single-attach_bgp_numbered/")))
    def test_single_bgp_numbered_data(self, testvar):
        _test_data('single-attach', 'bgp', 'numbered', testvar)

    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_single_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/single-attach_bgp_unnumbered/")))
    def test_single_bgp_numbered_data(self, testvar):
        _test_data('single-attach', 'bgp', 'unnumbered', testvar)

    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_single_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/single-attach_bgp_docker/")))
    def test_single_bgp_numbered_data(self, testvar):
        _test_data('single-attach', 'bgp', 'docker', testvar)

    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_single_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/single-attach_ospf_numbered/")))
    def test_single_ospf_numbered_data(self, testvar):
        _test_data('single-attach', 'ospf', 'numbered', testvar)

    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_single_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/single-attach_ospf_unnumbered/")))
    def test_single_ospf_numbered_data(self, testvar):
        _test_data('single-attach', 'ospf', 'unnumbered', testvar)

    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_single_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/single-attach_ospf_docker/")))
    def test_single_ospf_numbered_data(self, testvar):
        _test_data('single-attach', 'ospf', 'docker', testvar)

    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_single_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/single-attach_evpn_centralized/")))
    def test_single_evpn_centralized_data(self, testvar):
        _test_data('single-attach', 'evpn', 'centralized', testvar)

    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_single_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/single-attach_evpn_distributed/")))
    def test_single_evpn_distributed_data(self, testvar):
        _test_data('single-attach', 'evpn', 'distributed', testvar)

    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ or
                        'UPDATE_SQCMDS' in os.environ,
                        reason='Not updating data')
    @pytest.mark.depends(on=['test_create_single_data'])
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/single-attach_evpn_ospf-ibgp/")))
    def test_single_evpn_ospf_ibgp_data(self, testvar):
        _test_data('single-attach', 'evpn', 'ospf-ibgp', testvar)


# This isn't actually a test, it's just used to cleanup any stray vagrant state
@pytest.mark.cleanup
@pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                    reason='not sqpoller')
def test_cleanup_vagrant():
    devices = ['dual-attach_internet', 'dual-attach_spine01',
               'dual-attach_spine02', 'dual-attach_leaf01',
               'dual-attach_leaf02', 'dual-attach_leaf03',
               'dual-attach_leaf04', 'dual-attach_exit01',
               'dual-attach_exit02', 'dual-attach_server101',
               'dual-attach_server102', 'dual-attach_server103',
               'dual-attach_server104', 'dual-attach_edge01',
               'single-attach_internet', 'single-attach_spine01',
               'single-attach_spine02', 'single-attach_leaf01',
               'single-attach_leaf02', 'single-attach_leaf03',
               'single-attach_leaf04', 'single-attach_exit01',
               'single-attach_exit02', 'single-attach_server101',
               'single-attach_server102', 'single-attach_server103',
               'single-attach_server104', 'single-attach_edge01']
    for device in devices:
        out, ret, err = run_cmd(['virsh', 'destroy', device])
        print(f"virsh destroy {out} {err}")
        out, ret, err = run_cmd(['virsh', 'undefine', device])
        print(f"virsh undefine {out} {err}")
        out, ret, err = run_cmd(['virsh', 'vol-delete', f"{device}.img", '--pool', 'default'])
        print(f"virsh vol-delete {out} {err}")
    out, ret, err = run_cmd(['vagrant', 'global-status', '--prune'])
    print(f"global status {out} {err}")
