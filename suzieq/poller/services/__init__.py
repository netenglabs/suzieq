from os.path import isfile, isdir, dirname
import logging
import yaml
import textfsm
from pkgutil import walk_packages
from inspect import getmembers, isclass, getfile
import importlib
from collections import defaultdict
from pathlib import Path

from suzieq.utils import Schema, SchemaForTable
from .service import Service


logger = logging.getLogger(__name__)


def parse_nos_version(svc_dir, filename, svc_def, elem, val):

    if ("command" not in val) or (
        (
            isinstance(val["command"], list)
            and not all("textfsm" in x or "normalize" in x for x in val["command"])
        )
        or (
            not isinstance(val["command"], list)
            and ("normalize" not in val and "textfsm" not in val)
        )
    ):
        logger.error(
            "Ignoring invalid service file "
            'definition. Need both "command" and '
            '"normalize/textfsm" keywords: {}, {}'.format(
                filename, val)
        )
        return

    if "textfsm" in val:
        # We may have already visited this element and parsed
        # the textfsm file. Check for this
        if val["textfsm"] and isinstance(
            val["textfsm"], textfsm.TextFSM
        ) or (val["textfsm"] is None):
            return
        tfsm_file = svc_dir + "/" + val["textfsm"]
        if not isfile(tfsm_file):
            logger.error(
                "Textfsm file {} not found. Ignoring"
                " service".format(tfsm_file)
            )
            return
        with open(tfsm_file, "r") as f:
            tfsm_template = textfsm.TextFSM(f)
            val["textfsm"] = tfsm_template
    elif (isinstance(val['command'], list)):
        for subelem in val['command']:
            if 'textfsm' in subelem:
                if subelem["textfsm"] and isinstance(
                    subelem["textfsm"], textfsm.TextFSM
                ):
                    continue
                tfsm_file = svc_dir + "/" + subelem["textfsm"]
                if not isfile(tfsm_file):
                    logger.error(
                        "Textfsm file {} not found. Ignoring"
                        " service".format(tfsm_file)
                    )
                    continue
                with open(tfsm_file, "r") as f:
                    try:
                        tfsm_template = textfsm.TextFSM(f)
                        subelem["textfsm"] = tfsm_template
                    except Exception:
                        logger.exception(
                            'Unable to load TextFSM file '
                            f'{tfsm_file} for service '
                            f'{svc_def["service"]}')
                        continue
    else:
        tfsm_template = None


async def init_services(svc_dir: str, schema_dir: str, queue, svclist: list,
                        def_interval: int, run_once: str):
    """Process service definitions by reading each file in svc dir"""

    svcs_list = []
    schemas = defaultdict(dict)

    # Load up all the service definitions we can find
    svc_classes = {}
    for i in walk_packages(path=[dirname(getfile(Service))]):
        for mbr in getmembers(importlib.import_module(
                'suzieq.poller.services.'+i.name), isclass):
            if mbr[0] == "Service" or not mbr[0].endswith("Service"):
                continue
            svc_classes[i.name] = mbr[1]
            svc_classes[mbr[0]] = mbr[1]

    if not isdir(svc_dir):
        logger.error("services directory not a directory: {}".format(svc_dir))
        return svcs_list

    if not isdir(schema_dir):
        logger.error("schema directory not a directory: {}".format(svc_dir))
        return svcs_list
    else:
        schemas = Schema(schema_dir)

    if schemas:
        poller_schema = schemas.get_arrow_schema("sqPoller")
        poller_schema_version = SchemaForTable('sqPoller', schemas).version

    for filename in Path(svc_dir).glob('*.yml'):
        with open(filename, "r") as f:
            svc_def = yaml.safe_load(f.read())
        if svc_def.get('service') not in svclist:
            logger.warning(
                f'Ignoring unspecified service {svc_def.get("service")}'
            )
            continue

        if "service" not in svc_def or "apply" not in svc_def:
            logger.error(
                'Ignoring invalid service file definition. \
                 "service" and "apply" keywords: {}'.format(
                    filename
                )
            )
            continue

        period = svc_def.get("period", def_interval)
        for elem, val in svc_def["apply"].items():
            if isinstance(val, dict) and "copy" in val:
                newval = svc_def["apply"].get(val["copy"], None)
                if not newval:
                    logger.error(
                        "No device type {} to copy from for "
                        "{} for service {}".format(
                            val["copy"], elem, svc_def["service"]
                        )
                    )
                    return
                val = newval

            if isinstance(val, list):
                for subele in val:
                    parse_nos_version(svc_dir, filename, svc_def, elem,
                                      subele)
            else:

                parse_nos_version(svc_dir, filename, svc_def, elem, val)

        try:
            schema = SchemaForTable(svc_def['service'],
                                    schema=schemas)
        except Exception:
            logger.error(
                f"No matching schema for {svc_def['service']}")
            continue

        if schema.type == "derivedRecord":
            # These are not real services and so ignore them
            continue

        # Valid service definition, add it to list
        if svc_def["service"] in svc_classes:
            service = svc_classes[svc_def["service"]](
                svc_def["service"],
                svc_def["apply"],
                period,
                svc_def.get("type", "state"),
                svc_def.get("keys", []),
                svc_def.get("ignore-fields", []),
                schema,
                queue,
                run_once,
            )
        else:
            service = Service(
                svc_def["service"],
                svc_def["apply"],
                period,
                svc_def.get("type", "state"),
                svc_def.get("keys", []),
                svc_def.get("ignore-fields", []),
                schema,
                queue,
                run_once
            )

        service.poller_schema = poller_schema
        service.poller_schema_version = poller_schema_version
        logger.info("Service {} added".format(service.name))
        svcs_list.append(service)

    return svcs_list

__all__ = [Service, init_services]
