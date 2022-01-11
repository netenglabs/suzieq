import os
import glob
import shutil
import sys
from subprocess import check_output, check_call, CalledProcessError, STDOUT
import time
import logging
import json

import yaml
import pytest

# pylint: disable=wildcard-import
from suzieq.cli.sqcmds import *  # noqa
from suzieq.shared.utils import load_sq_config
from tests import conftest


# This is not just a set of tests, it will also update
#  the data collected for other test_sqcmds tests

ansible_file = \
    '/.vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory'
sqcmds_dir = 'tests/integration/sqcmds/'
UPDATE_SQCMDS = 'tests/utilities/update_sqcmds.py'
cndcn_samples_dir = 'tests/integration/all_cndcn/'
parquet_dir = '/tmp/suzieq-tests-parquet'


def copytree(src, dst, symlinks=False, ignore=None):
    '''Copy folders'''
    if not os.path.isdir(dst):
        os.makedirs(dst)
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
    '''Create dummy config'''
    # We need to create a tempfile to hold the config
    tmpconfig = load_sq_config(conftest.create_dummy_config_file())
    tmpconfig['data-directory'] = f"{t_dir}/parquet-out"
    tmpconfig['service-directory'] = \
        f"{suzieq_dir}/{tmpconfig['service-directory']}"
    tmpconfig['schema-directory'] = \
        f"{suzieq_dir}/{tmpconfig['schema-directory']}"

    fname = f'{t_dir}/suzieq-cfg.yml'

    with open(fname, 'w') as f:
        f.write(yaml.dump(tmpconfig))
    return fname


def run_cmd(cmd):
    '''Execute given cmd'''
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
    '''Return path to cdcn folder'''
    os.chdir(path)
    run_cmd(
        ['git', 'clone',
         'https://github.com/netenglabs/cloud-native-data-center-networking.git'])  # noqa
    return os.getcwd() + '/cloud-native-data-center-networking'

# pylint: disable=redefined-outer-name


def run_sqpoller_gather(name, ansible_dir, suzieq_dir, input_path):
    '''Run the poller to only collect raw data'''
    sqcmd_path = [sys.executable, f"{suzieq_dir}/suzieq/poller/sq_poller.py"]
    sqcmd = sqcmd_path + ['-a', ansible_dir + ansible_file, '-n', name,
                          '--run-once', 'gather', '--output-dir',
                          f'{input_path}/suzieq-input']
    _, code, _ = run_cmd(sqcmd)
    assert code == 0 or code is None


def run_sqpoller_process(files_dir, suzieq_dir, cfg_file):
    '''Run the poller to only collect processed output'''
    sqcmd_path = [sys.executable, f"{suzieq_dir}/suzieq/poller/sq_poller.py"]
    sqcmd = sqcmd_path + ['-i', files_dir, '-c', cfg_file]
    _, code, _ = run_cmd(sqcmd)
    assert code == 0 or code is None


def run_scenario(scenario):
    '''Run ansible playbook for given scenario'''
    run_cmd(['ansible-playbook', '-b', '-e', f'scenario={scenario}',
             'deploy.yml'])
    time.sleep(10)
    out, code, err = run_cmd(['ansible-playbook', 'ping.yml'])
    logging.warning(f"ping results {out} {code} {err}")
    print(f"ping results {out} {code} {err}")
    return out, code


# pylint: disable=redefined-outer-name
def check_suzieq_data(suzieq_dir, name, cfg_file, threshold='14'):
    '''Check cmd outputs to verify proper data gather'''
    sqcmd_path = [sys.executable, f"{suzieq_dir}/{conftest.suzieq_cli_path}"]
    sqcmd = sqcmd_path + ['device', 'unique', '--columns=namespace',
                          f'--namespace={name}', '--count=True', '-c',
                          cfg_file]
    out, _, err = run_cmd(sqcmd)
    # there should be 14 different hosts collected
    assert threshold in out, f'failed {out}, {err}'
    for cmd in ['bgp', 'interface', 'ospf', 'evpnVni']:
        sqcmd = sqcmd_path + [cmd, 'assert', f'--namespace={name}']
        out, code, err = run_cmd(sqcmd)
        assert code is None or code == 1 or code == 255


# pylint: disable=redefined-outer-name
def gather_data(topology, proto, scenario, name, suzieq_dir, input_path):
    '''Poll data and populate DB'''
    os.chdir(f"{topology}/{proto}")
    vagrant_up()
    _, code = run_scenario(scenario)
    if code is not None:
        logging.warning("retrying setting up scenario")
        vagrant_down()
        time.sleep(10)
        vagrant_up()
        run_scenario(scenario)
    folder = os.getcwd() + '/..'
    run_sqpoller_gather(name, folder, suzieq_dir, input_path)
    vagrant_down()
    # sleep_time = random.random() * 30
    time.sleep(120)
    os.chdir('../..')


# pylint: disable=redefined-outer-name
def update_data(name, files_dir, suzieq_dir, tmp_path, number_of_devices='14'):
    '''Update DB'''
    cfg_file = create_config(tmp_path, suzieq_dir)
    run_sqpoller_process(files_dir, suzieq_dir, cfg_file)
    check_suzieq_data(suzieq_dir, name, cfg_file, number_of_devices)

    return cfg_file


def vagrant_up():
    '''Spin up the topology'''
    logging.warning(f"VAGRANT dir {os.getcwd()}")
    print(f"VAGRANT dir {os.getcwd()}")
    run_cmd(['vagrant', 'up'])
    out, code, _ = run_cmd(['vagrant', 'status'])
    logging.warning(f"VAGRANT UP {out}")
    run_cmd(['vagrant', 'up'])
    out, code, _ = run_cmd(['vagrant', 'status'])
    logging.warning(f"VAGRANT UP {out}")
    return code


def vagrant_down():
    '''Shutdown the topology'''
    logging.warning("VAGRANT DOWN")
    run_cmd(['vagrant', 'destroy', '-f'])


# this is an attempt to clean up vagrant if something goes wrong
@pytest.fixture
def vagrant_setup():
    '''???'''
    yield
    vagrant_down()


def git_del_dir(folder):
    '''Del git dir'''
    if os.path.isdir(folder):
        try:
            check_call(['git', 'rm', '-rf', folder])
        except CalledProcessError:
            shutil.rmtree(folder)


def update_sqcmds(files, data_dir=None, namespace=None):
    '''Update tests'''
    for file in files:
        cmd = ['python3', UPDATE_SQCMDS, '-f', file, '-o']
        if data_dir:
            cmd += ['-d', data_dir]
        if namespace:
            cmd += ['-n', namespace]
        logging.warning(cmd)
        out, code, error = run_cmd(cmd)
        assert code is None or code == 0, \
            f"{file} failed, {out} {code} {error}"


def update_input_data(root_dir, nos, scenario, input_path):
    '''Update collected raw data used for tests'''
    dst_dir = f'{root_dir}/tests/integration/sqcmds/{nos}-input/{scenario}/'
    git_del_dir(dst_dir)
    copytree(f'{input_path}/suzieq-input', dst_dir)


class TestUpdate:
    '''Update the data'''
    @pytest.mark.test_update
    @pytest.mark.gather_data
    @pytest.mark.skipif(not os.environ.get('SUZIEQ_POLLER', None),
                        reason='Not gathering data')
    # pylint: disable=redefined-outer-name, unused-argument
    def test_gather_cumulus_data(self, tmp_path, vagrant_setup):
        '''Collect data for Cumulus, bgp'''
        orig_dir = os.getcwd()
        path = get_cndcn(tmp_path)
        os.chdir(path + '/topologies')

        gather_data('dual-attach', 'evpn', 'ospf-ibgp',
                    'ospf-ibgp', orig_dir, tmp_path)
        update_input_data(orig_dir, 'cumulus', 'ospf-ibgp', tmp_path)

        gather_data('dual-attach', 'evpn', 'centralized',
                    'dual-evpn', orig_dir, tmp_path)
        update_input_data(orig_dir, 'cumulus', 'dual-evpn', tmp_path)

        gather_data('single-attach', 'ospf', 'numbered',
                    'ospf-single', orig_dir, tmp_path)
        update_input_data(orig_dir, 'cumulus', 'ospf-single', tmp_path)

        gather_data('dual-attach', 'bgp', 'unnumbered',
                    'dual-bgp', orig_dir, tmp_path)
        update_input_data(orig_dir, 'cumulus', 'dual-bgp', tmp_path)

    @pytest.mark.test_update
    @pytest.mark.update_data
    @pytest.mark.cumulus
    @pytest.mark.skipif(not os.environ.get('SUZIEQ_POLLER', None),
                        reason='Not updating data')
    def test_update_cumulus_multidc_data(self, tmp_path):
        '''Collect data for Cumulus evpn, ospf'''
        orig_dir = os.getcwd()

        update_data(
            'ospf-ibgp',
            f'{orig_dir}/tests/integration/sqcmds/cumulus-input/ospf-ibgp',
            orig_dir, tmp_path)
        update_data(
            'dual-evpn',
            f'{orig_dir}/tests/integration/sqcmds/cumulus-input/dual-evpn',
            orig_dir, tmp_path)
        update_data(
            'ospf-single',
            f'{orig_dir}/tests/integration/sqcmds/cumulus-input/ospf-single',
            orig_dir, tmp_path)

        dst_dir = f'{orig_dir}/tests/data/multidc/parquet-out'
        git_del_dir(dst_dir)
        copytree(f'{tmp_path}/parquet-out', dst_dir)
        shutil.rmtree(f'{tmp_path}/parquet-out')

        update_data(
            'dual-bgp',
            f'{orig_dir}/tests/integration/sqcmds/cumulus-input/dual-bgp',
            orig_dir, tmp_path)

        dst_dir = f'{orig_dir}/tests/data/basic_dual_bgp/parquet-out'
        git_del_dir(dst_dir)

        copytree(f'{tmp_path}/parquet-out', dst_dir)
        shutil.rmtree(f'{tmp_path}/parquet-out')

        # update the samples data with updates from the newly collected data

        if os.environ.get('SUZIEQ_POLLER', None) != 'data':
            update_sqcmds(glob.glob(f'{sqcmds_dir}/cumulus-samples/*.yml'))

    def _update_test_data_common_fn(self, nos, tmp_path, device_cnt):
        '''Update tests data'''
        orig_dir = os.getcwd()

        update_data(nos, f'{orig_dir}/tests/integration/sqcmds/{nos}-input/',
                    orig_dir, tmp_path, number_of_devices=device_cnt)

        dst_dir = f'{orig_dir}/tests/data/{nos}/parquet-out'
        git_del_dir(dst_dir)
        copytree(f'{tmp_path}/parquet-out', dst_dir)
        shutil.rmtree(f'{tmp_path}/parquet-out')

        # update the samples data with updates from the newly collected data

        if os.environ.get('SUZIEQ_POLLER', None) != 'data':
            update_sqcmds(glob.glob(f'{sqcmds_dir}/{nos}-samples/*.yml'))

    @pytest.mark.test_update
    @pytest.mark.update_data
    @pytest.mark.eos
    @pytest.mark.skipif(not os.environ.get('SUZIEQ_POLLER', None),
                        reason='Not updating data')
    def test_update_eos_data(self, tmp_path):
        '''Update EOS test data'''
        self._update_test_data_common_fn('eos', tmp_path, '14')

    @pytest.mark.test_update
    @pytest.mark.update_data
    @pytest.mark.nxos
    @pytest.mark.skipif(not os.environ.get('SUZIEQ_POLLER', None),
                        reason='Not updating data')
    def test_update_nxos_data(self, tmp_path):
        '''Update NXOS test data'''
        self._update_test_data_common_fn('nxos', tmp_path, '14')

    @pytest.mark.test_update
    @pytest.mark.update_data
    @pytest.mark.junos
    @pytest.mark.skipif(not os.environ.get('SUZIEQ_POLLER', None),
                        reason='Not updating data')
    def test_update_junos_data(self, tmp_path):
        '''Update Junos test data'''
        self._update_test_data_common_fn('junos', tmp_path, '12')

    @pytest.mark.test_update
    @pytest.mark.update_data
    @pytest.mark.mixed
    @pytest.mark.skipif(not os.environ.get('SUZIEQ_POLLER', None),
                        reason='Not updating data')
    def test_update_mixed_data(self, tmp_path):
        '''Update test data for mixed sim, from Rick'''
        self._update_test_data_common_fn('mixed', tmp_path, '8')

    @pytest.mark.test_update
    @pytest.mark.update_data
    @pytest.mark.vmx
    @pytest.mark.skipif(not os.environ.get('SUZIEQ_POLLER', None),
                        reason='Not updating data')
    def test_update_vmx_data(self, tmp_path):
        '''Update test data for VMX'''
        self._update_test_data_common_fn('vmx', tmp_path, '5')


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


def _test_sqcmds(context_config, testvar):
    '''Workhorse fn to update Test data'''
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

        assert (isinstance(expected_jout, dict) == isinstance(jout, dict))

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
            (f"expected error, but got: output: {output}, error: {error}, "
             f"xfail: {testvar['xfail']}")
    else:
        raise Exception(f"either xfail or output requried {error}")

# pylint: disable=redefined-outer-name


def _gather_cndcn_data(topology, proto, scenario, input_path):
    '''Collect raw data for CDCN topologies'''
    orig_dir = os.getcwd()
    path = get_cndcn(input_path)
    # pylint: disable=redefined-outer-name
    name = f'{topology}_{proto}_{scenario}'
    os.chdir(path + '/topologies')
    dst_dir = f'{orig_dir}/tests/integration/all_cndcn/{name}-input'
    gather_data(topology, proto, scenario, name, orig_dir, input_path)
    git_del_dir(dst_dir)
    copytree(f'{input_path}/suzieq-input', dst_dir)
    os.chdir(orig_dir)


def _update_cndcn_data(topology, proto, scenario, tmp_path):
    '''Update local DB with data from topologies, CDCN topologies'''
    orig_dir = os.getcwd()
    # pylint: disable=redefined-outer-name
    name = f'{topology}_{proto}_{scenario}'

    update_data(name, f'{orig_dir}/tests/integration/all_cndcn/{name}-input',
                orig_dir, tmp_path)

    if not os.path.isdir(parquet_dir):
        os.mkdir(parquet_dir)
    if not os.path.isdir(f'{parquet_dir}/{name}'):
        os.mkdir(f'{parquet_dir}/{name}')

    copytree(f"{tmp_path}/parquet-out",
             f"{parquet_dir}/{name}/parquet-out/")

    if os.environ.get('UPDATE_SQCMDS', None):
        update_sqcmds(glob.glob(f'{cndcn_samples_dir}/{name}-samples/*.yml'),
                      data_dir=f"{parquet_dir}/{name}/parquet-out",
                      namespace=name)


def _test_data(topology, proto, scenario, testvar):
    # pylint: disable=redefined-outer-name
    name = f'{topology}_{proto}_{scenario}'
    testvar['data-directory'] = f"{parquet_dir}/{name}/parquet-out"
    dummy_config = load_sq_config(conftest.create_dummy_config_file())
    _test_sqcmds(dummy_config, testvar)


# these are grouped as classes so that we will only do one a time
#  when using --dist=loadscope
# because we have two vagrant files in CNDCN, that means we can run
# two simulations at a time, one single-attach and one dual-attach

class TestDualAttach:
    '''Update Tests and data for dual-attach topology'''
    topology = 'dual-attach'

    @pytest.mark.cndcn
    @pytest.mark.gather_dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("proto, scenario", tests)
    # pylint: disable=unused-argument
    def test_gather_dual_data(self, proto, scenario, tmp_path, vagrant_setup):
        '''Collect run-once=gather data for dual-attach topology'''
        _gather_cndcn_data(self.topology, proto, scenario, tmp_path)  # noqa

    @pytest.mark.update_dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("proto, scenario", tests)
    def test_update_dual_data(self, proto, scenario, tmp_path):
        '''Update parquet for dual-attach topology scenarios'''
        # this takes the data that was captured with run-once=gather
        #  and creates the parquet data
        #   if you also have UPDATE_SQCMDS in your os environment
        #   it will update the data in the samples directories
        _update_cndcn_data(self.topology, proto, scenario, tmp_path)

    # these needs to be run after the tests are created and updated
    # there is no way to have pytest run the load_up_the_tests before the
    # updater
    @pytest.mark.cndcn
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_bgp_numbered-samples/")))
    # pylint: disable=unused-argument
    def test_dual_bgp_numbered_data(self, testvar, tmp_path):
        '''Update test data for dual-attach numbered ospf'''
        proto = 'bgp'
        scenario = 'numbered'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             f'you need to run update_dual_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/dual-attach_bgp_unnumbered-samples/")))
    def test_dual_bgp_unnumbered_data(self, testvar):
        '''Update test data for dual-attach unnumbered bgp'''
        proto = 'bgp'
        scenario = 'unnumbered'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_dual_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_bgp_docker-samples/")))
    def test_dual_bgp_docker_data(self, testvar):
        '''Update test data for dual-attach bgp w/docker'''
        proto = 'bgp'
        scenario = 'docker'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_dual_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_ospf_numbered-samples/")))
    def test_dual_ospf_numbered_data(self, testvar):
        '''Update test data for dual-attach numbered ospf'''
        proto = 'ospf'
        scenario = 'numbered'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_dual_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/dual-attach_ospf_unnumbered-samples/")))
    def test_dual_ospf_unnumbered_data(self, testvar):
        '''Update test data for dual-attach unnumbered ospf'''
        proto = 'ospf'
        scenario = 'unnumbered'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_dual_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/dual-attach_ospf_docker-samples/")))
    def test_dual_ospf_docker_data(self, testvar):
        '''Update test data for dual-attach ospf w/docker'''
        proto = 'ospf'
        scenario = 'docker'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_dual_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/dual-attach_evpn_centralized-samples/")))
    def test_dual_evpn_centralized_data(self, testvar):
        '''Update test data for dual-attach centralized evpn'''
        proto = 'evpn'
        scenario = 'centralized'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_dual_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/dual-attach_evpn_distributed-samples/")))
    def test_dual_evpn_distributed_data(self, testvar):
        '''Update test data for dual-attach evpn'''
        proto = 'evpn'
        scenario = 'distributed'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_dual_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.dual_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/dual-attach_evpn_ospf-ibgp-samples/")))
    def test_dual_evpn_ospf_ibgp_data(self, testvar):
        '''Update test data for dual attach ospf-ibgp'''
        proto = 'evpn'
        scenario = 'ospf-ibgp'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_dual_attach test first')
        _test_data(self.topology, proto, scenario, testvar)


class TestSingleAttach:
    '''Update data and tests for single-attach topology'''
    topology = 'single-attach'

    @pytest.mark.cndcn
    @pytest.mark.gather_single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("proto, scenario", tests)
    # pylint: disable=unused-argument
    def test_gather_single_data(self, proto, scenario, tmp_path,
                                vagrant_setup):
        '''Collect run-once=gather data for single attach topology'''
        _gather_cndcn_data('single-attach', proto, scenario, tmp_path)

    @pytest.mark.update_single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("proto, scenario", tests)
    def test_update_single_data(self, proto, scenario, tmp_path):
        '''Update test data for single attach topology'''
        # this takes the data that was captured with run-once=gather
        #  and creates the parquet data
        #   if you also have UPDATE_SQCMDS in your os environment
        #   it will update the data in the samples directories
        _update_cndcn_data(self.topology, proto, scenario, tmp_path)

    # this needs to be run after the tests are created and updated
    # there is no way to have pytest run the load_up_the_tests before
    # the updater

    @pytest.mark.cndcn
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/single-attach_bgp_numbered-samples/")))
    def test_single_bgp_numbered_data(self, testvar):
        '''Update test data for single attach numbered BGP'''
        proto = 'bgp'
        scenario = 'numbered'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_single_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/single-attach_bgp_unnumbered-samples/")))
    def test_single_bgp_unnumbered_data(self, testvar):
        '''Update test data for single attach unnumbered BGP'''
        proto = 'bgp'
        scenario = 'unnumbered'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_single_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/single-attach_bgp_docker-samples/")))
    def test_single_bgp_docker_data(self, testvar):
        '''Update test data for single attach BGP w/Docker'''
        proto = 'bgp'
        scenario = 'docker'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_single_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/single-attach_ospf_numbered-samples/")))
    def test_single_ospf_numbered_data(self, testvar):
        '''Update test data for single attach numbered OSPF'''
        proto = 'ospf'
        scenario = 'numbered'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_single_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/single-attach_ospf_unnumbered-samples/")))
    def test_single_ospf_unnumbered_data(self, testvar):
        '''Update test data for single attach OSPF unnumbered'''
        proto = 'ospf'
        scenario = 'unnumbered'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_single_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(f"{cndcn_samples_dir}/single-attach_ospf_docker-samples/")))
    def test_single_ospf_docker_data(self, testvar):
        '''Update test data for single attach OSPF docker'''
        proto = 'ospf'
        scenario = 'docker'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_single_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/single-attach_evpn_centralized-samples/")))
    def test_single_evpn_centralized_data(self, testvar):
        '''Update test data for single attach centralized evpn'''
        proto = 'evpn'
        scenario = 'centralized'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_single_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/single-attach_evpn_distributed-samples/")))
    def test_single_evpn_distributed_data(self, testvar):
        '''Update test data for single attach evpn'''
        proto = 'evpn'
        scenario = 'distributed'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_single_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

    @pytest.mark.cndcn
    @pytest.mark.single_attach
    @pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                        reason='Not updating data')
    @pytest.mark.parametrize("testvar", conftest.load_up_the_tests(
        os.scandir(
            f"{cndcn_samples_dir}/single-attach_evpn_ospf-ibgp-samples/")))
    def test_single_evpn_ospf_ibgp_data(self, testvar):
        '''Update test data for single attach ospf ibgp'''
        proto = 'evpn'
        scenario = 'ospf-ibgp'
        name = f'{self.topology}_{proto}_{scenario}'
        assert os.path.isdir(f'{parquet_dir}/{name}'), \
            (f'missing {parquet_dir}/{name} directory. '
             'you need to run update_single_attach test first')
        _test_data(self.topology, proto, scenario, testvar)

# This isn't actually a test, it's just used to cleanup any stray vagrant state


@pytest.mark.cleanup
@pytest.mark.skipif('SUZIEQ_POLLER' not in os.environ,
                    reason='not sqpoller')
def test_cleanup_vagrant():
    '''Cleanup sim'''
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
        out, _, err = run_cmd(['virsh', 'destroy', device])
        print(f"virsh destroy {out} {err}")
        out, _, err = run_cmd(['virsh', 'undefine', device])
        print(f"virsh undefine {out} {err}")
        out, _, err = run_cmd(
            ['virsh', 'vol-delete', f"{device}.img", '--pool', 'default'])
        print(f"virsh vol-delete {out} {err}")
    out, _, err = run_cmd(['vagrant', 'global-status', '--prune'])
    print(f"global status {out} {err}")
