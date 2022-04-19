"""
This module contains the logic needed to parse the Suzieq native inventory
file
"""

import re
import sys
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Dict, List

import yaml
from pydantic import ValidationError
from suzieq.poller.controller.base_controller_plugin import ControllerPlugin
from suzieq.poller.controller.utils.inventory_models import (DeviceModel,
                                                             InventoryModel,
                                                             NamespaceModel)
from suzieq.shared.exceptions import InventorySourceError


@dataclass
class InventoryValidationError:
    """Dataclass for inventory errors handling.

    location: namespaces, sources, devices, auths
    name: name of the object raising an exception
    what: the raised exception
    """
    location: str
    name: str
    what: Exception


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

    inventory_data = {}
    with open(source_file, 'r') as fp:
        file_content = fp.read()
        try:
            inventory_data = yaml.safe_load(file_content)
        except Exception as e:
            raise InventorySourceError(f'Invalid Suzieq inventory file: {e}')

    return validate_raw_inventory(inventory_data)

    # for k in inventory:
    #     inventory[k] = get_inventory_config(k, inventory_data)

    # inventory['namespaces'] = inventory_data.get('namespaces')

    # return inventory


def validate_raw_inventory(inventory: dict) -> Dict:
    """Validate the inventory read from file and update its content
    to be easier to load into plugins

    Args:
        inventory (dict): inventory read from file

    Returns:
        Dict: updated inventory

    Raises:
        InventorySourceError: invalid inventory
    """
    # pylint: disable=too-many-nested-blocks
    # pylint: disable=broad-except

    def find_error(
            errors: List[InventoryValidationError],
            name: str, location: str) -> bool:
        """Checks if the name is already in errors
        It is used to avoid launching chained exceptions

        Args:
            errors (List[InventoryValidationError]): list of errors found
            name (str): name of the object who generated the error
            location (str): location of the name

        Returns:
            bool: True if the name is found
        """
        # pylint: disable=used-before-assignment
        # I think it is a bug of pylint. It tells me that e.name
        # is used before assignement
        return any((True for e in errors
                    if (e.location == location and e.name == name)))

    if not inventory:
        raise InventorySourceError('The inventory is empty')

    if not isinstance(inventory, dict):
        raise InventorySourceError(
            'Expected mapping instead of list. Check the docs to know how to '
            'build the inventory file')

    try:
        inv_model = InventoryModel(**inventory)
    except ValidationError as e:
        output_inv_errors([
            InventoryValidationError(
                location='inventory',
                name='',
                what=e
            )])
    new_inventory = {k: {} for k in inv_model.dict()}
    base_plugins = ControllerPlugin.get_plugins()
    errors: List[InventoryValidationError] = []
    for mf, fields in inv_model.dict().items():
        if not fields:
            # 'devices' and 'auths' can be omitted if not needed
            continue
        if mf == 'namespaces':
            # namespaces are validated later
            continue

        global_specs = {}
        for plugin_specs in fields:
            try:
                if 'copy' in plugin_specs:
                    # copy the content of the other inventory
                    # into the current inventory and override
                    # values
                    copyname = plugin_specs['copy']
                    if copyname not in global_specs:
                        if not find_error(errors, copyname, mf):
                            raise InventorySourceError(
                                "copy value must be a 'name' of an already "
                                f"defined {mf}: {copyname} not found"
                            )
                        else:
                            # an error related to 'copyname' was already raised
                            continue
                    plugin_specs = copy_inventory_item(
                        global_specs[copyname]['specs'], plugin_specs)

                if mf == 'auths':
                    # I don't like this step, but there is no other way
                    # to validate credentials otherwise
                    # In a future release I will rename credential_loader to
                    # auth and get rid of this if
                    mtype = 'credential_loader'
                else:
                    # remove the trailing 's'
                    mtype = mf[:-1]

                if mtype in base_plugins:
                    # validate 'auths' and 'sources'
                    base_plugin_class = base_plugins[mtype]
                    ptype = plugin_specs.get(
                        'type', base_plugin_class.default_type())\
                        .replace('-', '_')
                    plugin_class = base_plugin_class.get_plugins(ptype)\
                        .get(ptype)
                    if not plugin_class:
                        raise InventorySourceError(
                            f'Unknown {mf} of type {ptype}')
                    try:
                        model_class = plugin_class.get_data_model()
                    except NotImplementedError:
                        raise InventorySourceError(
                            f'Data model not implemented for {ptype}')
                    validated_obj = model_class(**plugin_specs)
                    name = validated_obj.name

                elif mf == 'devices':
                    # validate 'devices'
                    validated_obj = DeviceModel(**plugin_specs)
                    name = validated_obj.name

                if name in global_specs:
                    raise InventorySourceError(
                        f'{mf}.{name} is not unique')
                global_specs[name] = {
                    'validated': validated_obj.dict(by_alias=True),
                    'specs': plugin_specs
                }
            except Exception as e:
                errors.append(
                    InventoryValidationError(
                        location=mf,
                        name=plugin_specs.get('name'),
                        what=e
                    )
                )
        new_inventory[mf] = {name: g['validated']
                             for name, g in global_specs.items()}

    # validate 'namespaces'
    global_ns_specs = []
    for ns_specs in inv_model.namespaces:
        try:
            ns = NamespaceModel(**ns_specs)
        except Exception as e:
            errors.append(
                InventoryValidationError(
                    location='namespaces',
                    name=ns_specs.get('name'),
                    what=e
                )
            )
            continue
        for field, value in ns.dict().items():
            if field == 'name':
                continue
            inv_field = field + 's'
            try:
                if value and value not in new_inventory[inv_field]:
                    if find_error(errors, value, inv_field):
                        # an error already raised for this object
                        continue
                    raise InventorySourceError(
                        f"No {field} called '{value}'")
            except Exception as e:
                errors.append(
                    InventoryValidationError(
                        location='namespaces',
                        name=ns_specs.get('name'),
                        what=e
                    )
                )

        global_ns_specs.append(ns.dict(by_alias=True))
    new_inventory['namespaces'] = global_ns_specs

    if errors:
        output_inv_errors(errors)

    return new_inventory


def output_inv_errors(errors: List[InventoryValidationError]):
    """Creates a good looking output for inventory errors

    Args:
        errors (List[Exception]): list of errors found
    """

    error_str = '\n'
    for e in errors:
        error_str += f'- {e.location}'
        if e.name:
            error_str += f'.{e.name}'
        error_str += ':\n'
        if isinstance(e.what, ValidationError):
            for ve in e.what.errors():
                field = '.'.join(map(str, ve.get('loc', [''])))
                error_str += f"  + {field}: {ve.get('msg','')}\n"
        else:
            error_str += f'  + {str(e.what)}\n'
        error_str += '\n'
    raise InventorySourceError(error_str)


def copy_inventory_item(orig: Dict, dest: Dict) -> Dict:
    """Copy the content of orig inside dest for parameters not
    specified in dest

    Args:
        orig (Dict): original dict to copy
        dest (Dict): destination dict to update

    Returns:
        Dict: updated destination dict
    """
    for k, v in orig.items():
        if k not in dest:
            dest[k] = v
    if 'copy' in dest:
        dest.pop('copy')
    return dest


def validate_hostname(in_hostname: str) -> bool:
    """Validates if the hostname is an ip address or a domain

    Args:
        in_hostname (str): hostname to evaluate

    Returns:
        bool: validation result
    """
    try:
        ip_address(in_hostname)
        if sys.version_info[:3] < (3, 8, 12):
            # for python versions before 3.8.12, the ip_address function
            # doesn't tolerate addresses having octets with leading 0, like
            # "10.00.0.1"
            # The following regex makes the validation consistent across
            # python versions
            wrong_ip_pattern = r'(\.0\d+\.?)|(^0\d+\.?)'
            if re.search(wrong_ip_pattern, in_hostname):
                return False
        return True
    except ValueError:
        # check if it was a misspelled ipv4
        ipv4_pattern = r'^(\d+\.?)+$'
        if re.fullmatch(ipv4_pattern, in_hostname):
            # if this pattern matches, it means that the function
            # ip_address raise an error due to the fact of an misspelled ipv4
            # e.g. 10.0.1 or 10.0.2555.1
            return False

        # validate the domain name
        pattern = r'^([a-zA-Z0-9-.]{1,253})?$'
        m = re.fullmatch(pattern, in_hostname)

        if not m:
            return False

        hostname = m.groups()[0]

        # strip trailing dot if any
        hostname = hostname.strip('.')

        if len(hostname) > 253:
            return False

        for label in hostname.split('.'):
            lm = re.fullmatch(r'^([a-zA-Z0-9-]+)$', label)
            if lm and len(label) < 64 and \
                    not (label.startswith('-') or label.endswith('-')):
                continue
            else:
                return False
        return True
