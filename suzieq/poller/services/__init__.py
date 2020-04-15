from os.path import isfile, isdir, dirname
from os import walk
import logging
import yaml
import textfsm
from pkgutil import walk_packages
from inspect import getmembers, isclass, getfile
import importlib
from collections import defaultdict

from suzieq.utils import Schema
from .service import Service


logger = logging.getLogger(__name__)


async def init_services(svc_dir, schema_dir, queue, run_once):
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

    for root, _, filenames in walk(svc_dir):
        for filename in filenames:
            if filename.endswith(".yml") or filename.endswith(".yaml"):
                with open(root + "/" + filename, "r") as f:
                    svc_def = yaml.safe_load(f.read())
                if "service" not in svc_def or "apply" not in svc_def:
                    logger.error(
                        'Ignoring invalid service file definition. \
                    Need both "service" and "apply" keywords: {}'.format(
                            filename
                        )
                    )
                    continue

                period = svc_def.get("period", 15)
                for elem, val in svc_def["apply"].items():
                    if "copy" in val:
                        newval = svc_def["apply"].get(val["copy"], None)
                        if not newval:
                            logger.error(
                                "No device type {} to copy from for "
                                "{} for service {}".format(
                                    val["copy"], elem, svc_def["service"]
                                )
                            )
                            continue
                        val = newval

                    if "command" not in val or (
                        "normalize" not in val and "textfsm" not in val
                    ):
                        logger.error(
                            "Ignoring invalid service file "
                            'definition. Need both "command" and '
                            '"normalize/textfsm" keywords: {}, {}'.format(
                                filename, val)
                        )
                        continue

                    if "textfsm" in val:
                        # We may have already visited this element and parsed
                        # the textfsm file. Check for this
                        if val["textfsm"] and isinstance(
                            val["textfsm"], textfsm.TextFSM
                        ):
                            continue
                        tfsm_file = svc_dir + "/" + val["textfsm"]
                        if not isfile(tfsm_file):
                            logger.error(
                                "Textfsm file {} not found. Ignoring"
                                " service".format(tfsm_file)
                            )
                            continue
                        with open(tfsm_file, "r") as f:
                            tfsm_template = textfsm.TextFSM(f)
                            val["textfsm"] = tfsm_template
                    else:
                        tfsm_template = None

                try:
                    schema = schemas.get_arrow_schema(svc_def['service'])
                except Exception:
                    logger.error(
                        f"No matching schema for {svc_def['service']}")
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
                        run_once
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
                logger.info("Service {} added".format(service.name))
                svcs_list.append(service)

    return svcs_list

__all__ = [Service, init_services]
