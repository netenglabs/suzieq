from typing import Dict


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
