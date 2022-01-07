import argparse
import os
from typing import Dict
from pathlib import Path

import pytest
from suzieq.poller.controller.controller import (DEFAULT_INVENTORY_PATH,
                                                 Controller)
from suzieq.shared.exceptions import InventorySourceError
from suzieq.shared.utils import load_sq_config, sq_get_config_file
from tests.conftest import create_dummy_config_file

# pylint: disable=protected-access

_CONFIG_FILE = ['tests/unit/poller/controller/data/suzieq-cfg.yaml']

_INVENTORY_FILE = ['tests/unit/poller/controller/data/inventory.yaml']

_ARGS = [
    {
        'inventory': '',
        'input_dir': None,
        'config': '',
        'debug': True,
        'exclude_services': 'macs',
        'no_coalescer': True,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 3
    },
    {
        'inventory': '',
        'input_dir': 'tests/unit/poller/controller/data',
        'config': '',
        'debug': False,
        'exclude_services': 'macs',
        'no_coalescer': True,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 3
    },
    {
        'inventory': '',
        'input_dir': None,
        'config': '',
        'debug': False,
        'exclude_services': 'macs',
        'no_coalescer': False,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': 'gather',
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 3
    },
    {
        'inventory': '',
        'input_dir': None,
        'config': '',
        'debug': False,
        'exclude_services': 'macs',
        'no_coalescer': False,
        'outputs': 'parquet',
        'output_dir': 'outdir',
        'run_once': None,
        'service_only': 'topmem routes',
        'ssh_config_file': 'config/file',
        'update_period': 100,
        'workers': 3
    }
]


def update_args(args: Dict, inv_file: str, conf_file: str) -> Dict:
    args['inventory'] = inv_file
    args['config'] = conf_file
    return args


def generate_argparse(args: Dict) -> argparse.Namespace:
    return argparse.Namespace(**args)


@pytest.mark.poller
@pytest.mark.controller
@pytest.mark.parametrize('config_file', _CONFIG_FILE)
@pytest.mark.parametrize('inv_file', _INVENTORY_FILE)
@pytest.mark.parametrize('args', _ARGS)
def test_valid_controller_config(config_file: str, inv_file: str, args: Dict):

    args = update_args(args, inv_file, config_file)

    config = load_sq_config(config_file=config_file)

    parse_args = generate_argparse(args)

    c = Controller(parse_args, config)

    poller_config = config['poller']

    assert c._input_dir == args['input_dir']

    if args['debug']:
        assert c.run_once == 'debug'
    elif args['input_dir']:
        assert c.run_once == 'input-dir'
    else:
        assert c.run_once == args['run_once']

    if not args['input_dir']:
        assert c._config['source']['path'] == args['inventory']

    assert c._config['manager']['type'] == poller_config['manager']['type']
    assert c._config['chunker']['type'] == poller_config['chunker']['type']
    assert c.inventory_timeout == poller_config['inventory-timeout']
    if not args['run_once']:
        assert c._no_coalescer == args['no_coalescer']
    else:
        assert c._no_coalescer is True
    assert c.period == args['update_period']

    manager_args = ['debug', 'exclude-services', 'outputs', 'config',
                    'output-dir', 'service-only', 'ssh-config-file', 'workers']
    for ma in manager_args:
        args_key = ma.replace('-', '_')
        assert c._config['manager'][ma] == args[args_key]


@pytest.mark.poller
@pytest.mark.controller
def test_default_controller_config():
    default_args = {
        'inventory': None,
        'input_dir': None,
        'config': None,
        'debug': False,
        'exclude_services': None,
        'no_coalescer': False,
        'outputs': 'parquet',
        'output_dir': f'{os.path.abspath(os.curdir)}/sqpoller-output',
        'run_once': None,
        'service_only': None,
        'ssh_config_file': None,
        'update_period': None,
        'workers': None
    }

    conf_file = create_dummy_config_file()
    config = load_sq_config(config_file=conf_file)

    parse_args = generate_argparse(default_args)

    # no inventory file in default directory
    with pytest.raises(InventorySourceError):
        Controller(parse_args, config)

    # This is not working
    # The file is never created
    def_file = Path(DEFAULT_INVENTORY_PATH)
    def_file.touch(exist_ok=False)

    c = Controller(parse_args, config)
    assert c._config['source']['path'] == DEFAULT_INVENTORY_PATH
    assert c._input_dir is None
    assert c._no_coalescer is False
    assert c._config['manager']['config'] == sq_get_config_file(None)
    assert c._config['manager']['workers'] == 1
    assert c.period == 3600
    assert c.run_once is None
    manager_args = ['debug', 'exclude-services', 'outputs',
                    'output-dir', 'service-only', 'ssh-config-file']
    for ma in manager_args:
        args_key = ma.replace('-', '_')
        assert c._config['manager'][ma] == default_args[args_key]

    # Remove the default inventory file
    os.remove(def_file)
