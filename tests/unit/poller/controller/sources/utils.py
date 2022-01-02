from typing import Dict
import yaml


def get_sample_config(src_type: str) -> Dict:
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

    return sample_config


def read_result_data(path: str) -> Dict:
    """Read result from file

    Args:
        path (str): path of result file

    Returns:
        [Dict]: content of the file
    """
    return yaml.safe_load(open(path, 'r'))
