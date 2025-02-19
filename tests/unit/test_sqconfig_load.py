import re
from tempfile import NamedTemporaryFile
from unittest.mock import MagicMock, patch

import pytest
from suzieq.shared.utils import (get_sq_install_dir, load_sq_config,
                                 validate_sq_config)
from tests.conftest import create_dummy_config_file
from suzieq.shared.context import SqContext
from suzieq.cli.sqcmds import context_commands
from dataclasses import dataclass

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


@ pytest.mark.sq_config
@ pytest.mark.rest
def test_config_rest():
    #with pandas engine
    cfg = {'rest': {}}

    ctxt = SqContext(cfg=cfg)
    #check that the default value are the same
    assert ctxt.rest_transport == 'https'
    assert ctxt.rest_server_ip == '127.0.0.1'
    assert ctxt.rest_server_port == 8000
    assert ctxt.rest_api_key == ''
    assert ctxt.engine == 'pandas'

    # defining rest engine params
    cfg['rest']['API_KEY'] = '496157e6e869ef7f3d6ecb24a6f6d847b224ee4f'
    cfg['rest']['address'] = '0.0.0.0'
    cfg['rest']['port'] = 8000
    cfg['rest']['no-https'] = True
    cfg['ux']= {'engine': 'rest'}

    ctxt = SqContext(cfg=cfg)
    assert ctxt.rest_transport == 'http'
    assert ctxt.rest_server_ip == '0.0.0.0'
    assert ctxt.rest_server_port == 8000
    assert ctxt.rest_api_key == '496157e6e869ef7f3d6ecb24a6f6d847b224ee4f'
    assert ctxt.engine == 'rest'

    #https with rest engine
    cfg['rest']['no-https'] = False
    ctxt = SqContext(cfg=cfg)
    assert ctxt.rest_transport == 'https'
    assert ctxt.rest_server_ip == '0.0.0.0'
    assert ctxt.rest_server_port == 8000
    assert ctxt.rest_api_key == '496157e6e869ef7f3d6ecb24a6f6d847b224ee4f'
    assert ctxt.engine == 'rest'





@ pytest.mark.sq_config
@ pytest.mark.rest
def test_context_commands_context(monkeypatch):
    CTXT_REST_ATTRS = {
                'rest_server_ip': 'address',
                'rest_server_port': 'port',
                'rest_transport': 'no-https',
                'rest_api_key': 'API_KEY'}

    @dataclass
    class fake_ctxt_class():
        engine = 'rest'
        cfg = {'rest': 
               {
                'address': '0.0.0.0',
                'port': '8000',
                'no-https': True,
                'API_KEY': '496157e6e869ef7f3d6ecb24a6f6d847b224ee4f'
                }}
        rest_server_ip: str = 'test_rest_server_ip'
        rest_server_port: int = 8080
        rest_api_key: str = 'test_rest_api_key'
        rest_transport: str = 'test_rest_transport'

    @dataclass
    class fake_context_class():
        ctxt = fake_ctxt_class()

        def change_engine(self, engine):
            self.ctxt.engine = engine

    def fake_get_context():
        return fake_context_class()


    #sending set engine: rest when is already selected, nothing should change
    monkeypatch.setattr(context_commands.context,
                        'get_context',
                        fake_get_context)
    context_commands.set_ctxt(engine='rest')
    assert context_commands.context.get_context().ctxt.engine == 'rest'
    assert getattr(context_commands.context.get_context().ctxt,
                   'rest_server_ip') == 'test_rest_server_ip'
    assert getattr(context_commands.context.get_context().ctxt,
                   'rest_server_port') == 8080
    assert getattr(context_commands.context.get_context().ctxt,
                   'rest_api_key') == 'test_rest_api_key'
    assert getattr(context_commands.context.get_context().ctxt,
                   'rest_transport') == 'test_rest_transport'


    #sending set engine: rest when is selected engine: pandas with http  
    fake_context_class.ctxt.engine = 'pandas'
    monkeypatch.setattr(context_commands.context,
                        'get_context',
                        fake_get_context)
    context_commands.set_ctxt(engine='rest')
    assert context_commands.context.get_context().ctxt.engine == 'rest'
    for attr in CTXT_REST_ATTRS:
        #get the expexted value of the rest param
        expected_value = fake_ctxt_class.cfg['rest'][CTXT_REST_ATTRS[attr]]
        if CTXT_REST_ATTRS[attr] == 'no-https':
            expected_value = 'http' if expected_value == True else 'https'
        #check if all the rest attr match
        assert getattr(
            context_commands.context.get_context().ctxt,
            attr) == expected_value, f'{attr} value shold be {expected_value},\
            not {getattr(context_commands.context.get_context().ctxt, attr)}'

    
    #sending set engine: rest when is selected engine: pandas with https
    fake_context_class.ctxt.engine = 'pandas'
    fake_ctxt_class.cfg['rest']['no-https'] = False
    monkeypatch.setattr(context_commands.context,
                        'get_context',
                        fake_get_context)
    context_commands.set_ctxt(engine='rest')
    assert context_commands.context.get_context().ctxt.engine == 'rest'
    for attr in CTXT_REST_ATTRS:
        #get the expexted value of the rest param
        expected_value = fake_ctxt_class.cfg['rest'][CTXT_REST_ATTRS[attr]]
        if CTXT_REST_ATTRS[attr] == 'no-https':
            expected_value = 'http' if expected_value == True else 'https'
        #check if all the rest attr match
        assert getattr(
            context_commands.context.get_context().ctxt,
            attr) == expected_value, f'{attr} value shold be {expected_value},\
            not {getattr(context_commands.context.get_context().ctxt, attr)}'
