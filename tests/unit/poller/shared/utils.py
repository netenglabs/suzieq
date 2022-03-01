import random
import socket
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
from faker.proxy import Faker
from suzieq.poller.controller.credential_loader.static import StaticLoader


def get_random_node_list(inventory_size: int = 200) -> Tuple[Dict, Dict, Dict]:
    """Generate a list of random devices

    Args:
        inventory_size (int): Number of nodes in the list. Default 200

    Returns:
        Tuple[Dict, Dict, Dict]: Three dictionaries containing: device info,
            credentials, and a combination of the two dictionaries
    """
    inventory = {}
    credentials = {}
    all_nodes = {}

    fake = Faker()
    Faker.seed(random.randint(1, 10000))

    ports = [22, 443, 1244, 8080, 4565]
    transports = ['ssh', 'https', 'http']
    devtypes = ['panos', 'eos', None]
    namespaces = ['data-center-north', 'south-data-center']
    keys = ['tests/unit/poller/shared/sample_key', None]
    for _ in range(inventory_size):
        entry = {
            'address': fake.ipv4(address_class='c'),
            'username': fake.domain_word(),
            'port': fake.word(ports),
            'transport': fake.word(transports),
            'devtype': fake.word(devtypes),
            'namespace': fake.word(namespaces),
            'jump_host': fake.word([f"// {fake.domain_word()}@{fake.ipv4()}",
                                   None])
        }

        cred = {
            'password': fake.password(),
            'ssh_keyfile': fake.word(keys),
            'jump_host_key_file': fake.word(keys),
            'passphrase': fake.word([fake.password(), None])
        }
        key = f"{entry['namespace']}.{entry['address']}.{entry['port']}"
        inventory[key] = entry
        credentials[key] = cred
        all_nodes[key] = cred.copy()
        all_nodes[key].update(entry)
    return inventory, credentials, all_nodes


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
                'name': 'static0',
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


def get_free_port() -> int:
    """Return a free port

    Returns:
        int: free port
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]
