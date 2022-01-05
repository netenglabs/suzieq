from pathlib import Path
from typing import Any, Dict

import yaml
from suzieq.poller.controller.credential_loader.static import StaticLoader


def get_src_sample_config(src_type: str) -> Dict:
    """Return a sample configuration

    Args:
        src_type (str): source plugin type

    Returns:
        [Dict]: sample configuration
    """

    sample_config = {
        'name': f'{src_type}0',
        'namespace': f'{src_type}-ns',
        'type': f'{src_type}',
    }

    if src_type == 'ansible':
        sample_config.update({'path': ''})
    elif src_type == 'native':
        sample_config.update({'hosts': []})
    elif src_type == 'netbox':
        sample_config.update({
            'token': 'MY-TOKEN',
            'url': 'http://127.0.0.1:9000',
            'tag': 'suzieq',
            'run_once': True,
            'auth': StaticLoader({
                'username': 'username',
                'password': 'plain:password'
            }),
        })

    return sample_config


def read_yaml_file(path: str) -> Any:
    """Read result from file

    Args:
        path (str): path of result file

    Returns:
        [Any]: content of the file
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise RuntimeError(f'Invalid file to read {path}')
    return yaml.safe_load(open(file_path, 'r'))
