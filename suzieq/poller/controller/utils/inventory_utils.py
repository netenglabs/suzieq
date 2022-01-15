"""
This module contains the logic needed to parse the Suzieq native inventory
file
"""
from pathlib import Path
from typing import Dict

import yaml
from suzieq.shared.exceptions import InventorySourceError


def read_inventory(source_file: str) -> Dict:
    """Read the Suzieq native inventory returning a dictionary with its
    content.

    Args:
        source_path (str): the source file

    Raises:
        InventorySourceError: raised if there is any error if the file parsing

    Returns:
        Dict: a dictionary containing the content of the native inventory file
    """
    if not Path(source_file).is_file():
        raise InventorySourceError(
            f"Inventory file {source_file} doesn't exits")

    inventory = {
        'sources': {},
        'devices': {},
        'auths': {}
    }

    inventory_data = {}
    with open(source_file, 'r') as fp:
        file_content = fp.read()
        try:
            inventory_data = yaml.safe_load(file_content)
        except Exception as e:
            raise InventorySourceError(f'Invalid Suzieq inventory file: {e}')

    validate_raw_inventory(inventory_data)

    for k in inventory:
        inventory[k] = get_inventory_config(k, inventory_data)

    inventory['namespaces'] = inventory_data.get('namespaces')

    return inventory


def validate_raw_inventory(inventory: dict):
    """Validate the inventory read from file

    Args:
        inventory (dict): inventory read from file

    Raises:
        InventorySourceError: invalid inventory
    """
    if not inventory:
        raise InventorySourceError('The inventory is empty')

    for f in ['sources', 'namespaces']:
        if f not in inventory:
            raise InventorySourceError(
                "'sources' and 'namespaces' fields must be specified")

    main_fields = {
        'sources': [],
        'devices': [],
        'auths': [],
    }
    for mf, mf_list in main_fields.items():
        fields = inventory.get(mf)
        if not fields:
            # 'devices' and 'auths' can be omitted if not needed
            continue
        if not isinstance(fields, list):
            raise InventorySourceError(f'{mf} content must be a list')
        for value in fields:
            name = value.get('name')
            if not name:
                raise InventorySourceError(
                    f"{mf} items must have a 'name'")
            if name in mf_list:
                raise InventorySourceError(f'{mf}.{name} is not unique')
            mf_list.append(name)

            if not isinstance(value, dict):
                raise InventorySourceError(
                    f"{mf}.{name} is not a dictionary")

            if value.get('copy') and not value['copy'] in mf_list:
                raise InventorySourceError(f'{mf}.{name} value must be a '
                                           "'name' of an already defined "
                                           f'{mf} item')
    # validate 'namespaces'
    ns_fields = ['name', 'source', 'device', 'auth']
    for ns in inventory.get('namespaces'):

        if not ns.get('name'):
            raise InventorySourceError(
                "all namespaces need 'name' field")

        inv_fields = [x for x in ns if x not in ns_fields]
        if inv_fields:
            raise InventorySourceError(
                f'{ns["name"]} invalid fields {inv_fields}'
            )

        if not ns.get('source'):
            raise InventorySourceError(
                f"{ns['name']} all namespaces need 'source' field")

        if ns.get('source') not in main_fields['sources']:
            raise InventorySourceError(
                f"{ns['name']} No source called '{ns['source']}'")

        if ns.get('device') and ns['device'] not in main_fields['devices']:
            raise InventorySourceError(
                f"{ns['name']} No device called '{ns['device']}'")

        if ns.get('auth') and ns['auth'] not in main_fields['auths']:
            raise InventorySourceError(
                f"{ns['name']} No auth called '{ns['auth']}'")


def get_inventory_config(conf_type: str, inventory: dict) -> dict:
    """Return the configuration for a the config type as input

    The returned value will contain a dictionary with 'name' as key
    and the config as value

    Args:
        conf_type (str): type of configuration to initialize
        inventory (dict): inventory to read to collect configuration

    Returns:
        dict: configuration data
    """
    configs = {}
    conf_list = inventory.get(conf_type)
    if not conf_list:
        # No configuration specified
        return {}

    for conf_obj in conf_list:
        name = conf_obj.get('name')
        if name:
            if conf_obj.get('copy'):
                # copy the content of the other inventory
                # into the current inventory and override
                # values
                configs[name] = configs[conf_obj['copy']].copy()
                for k, v in conf_obj.items():
                    if k not in ['copy']:
                        configs[name][k] = v
            else:
                configs[name] = conf_obj

    return configs
