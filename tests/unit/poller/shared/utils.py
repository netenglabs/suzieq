import random
from typing import Dict, Tuple

from faker.proxy import Faker


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
