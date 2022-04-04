import re
from tempfile import NamedTemporaryFile
from unittest.mock import MagicMock, patch

import pytest
from suzieq.shared.utils import (get_sq_install_dir, load_sq_config,
                                 validate_sq_config)
from tests.conftest import create_dummy_config_file


@pytest.mark.sq_config
def test_valid_sq_config():
    """Test if the config is loaded correctly
    """
    cfg_file = create_dummy_config_file()

    exp_cfg = {
        'analyzer': {'timezone': 'GMT'},
        'data-directory': './tests/data/parquet',
        'logging-level': 'WARNING',
        'rest': {'API_KEY': '68986cfafc9d5a2dc15b20e3e9f289eda2c79f40'},
        'temp-directory': '/tmp/suzieq',
        'service-directory': f'{get_sq_install_dir()}/config',
        'schema-directory': f'{get_sq_install_dir()}/config/schema',
        'poller': {'logging-level': 'WARNING'}}

    cfg = load_sq_config(config_file=cfg_file)
    cfg.pop('test_set', None)

    assert cfg == exp_cfg, 'SqConfig not correctly loaded'


@pytest.mark.sq_config
def test_invalid_config_files(capsys):
    """Test empty or invalid config files
    """
    cfg_file = './this-file-doesnt-exits'

    try:
        load_sq_config(config_file=cfg_file)
        assert False, 'No error raised for an invalid config file'
    except SystemExit:
        error = capsys.readouterr().out
        assert re.match('ERROR: Unable to open config file.*', error)

    with NamedTemporaryFile(suffix='yml') as tmpfile:
        try:
            load_sq_config(config_file=tmpfile.name)
        except SystemExit:
            error = capsys.readouterr().out
            assert re.match('ERROR: Empty config file.*', error)


@pytest.mark.sq_config
def test_config_validation(monkeypatch):
    """Test the sq config validation
    """

    base_cfg = load_sq_config(config_file=create_dummy_config_file())

    # not a dict
    cfg = []
    error = validate_sq_config(cfg)
    assert error == "FATAL: Invalid config file format", 'Accepted an '\
        'invalid format'

    # no data-directory field
    cfg = {}
    error = validate_sq_config(cfg)
    assert error == "FATAL: No data directory for output files specified", \
        'Accepted config without "data-directory" parameter'

    # no svc-directory
    cfg['data-directory'] = base_cfg.get('data-directory')

    with patch('suzieq.shared.utils.get_sq_install_dir', MagicMock()):
        error = validate_sq_config(cfg)
        assert error == 'FATAL: No service directory found', \
            'Accepted config without a service directory set'

    env_var = 'REST_KEY'
    env_key = 'MY_KEY'
    # wrong env variable
    cfg['rest'] = {'API_KEY': f'env:{env_var}'}
    error = validate_sq_config(cfg)
    assert re.match('Cannot load REST API KEY.*', error), \
        'Error not raised for an invalid REST key environment variable'

    # correct env variable
    monkeypatch.setenv(env_var, env_key)
    error = validate_sq_config(cfg)
    assert error is None, error
