import importlib
from pkgutil import walk_packages
from inspect import getmembers, isclass


def get_class_by_path(
    module: str,
    module_path: str,
    base_class_module: str,
    base_class_name: str = ""
):
    """
    Return a dictionary containing the classes inside <path>

    path: dotted path from which import the module
    base_class_path: absolute path where to find modules
    base_class_name: used to filter the members
    """

    classes = {}
    base_class = {}
    for bmbr in getmembers(
        importlib.import_module(base_class_module), isclass
    ):
        if bmbr[0] == base_class_name:
            base_class = bmbr[1]
            break

    if not base_class:
        raise RuntimeError(
            "Base class {} not found at {}"
            .format(base_class_name, base_class_module)
        )

    for i in walk_packages([module_path]):
        for mbr in getmembers(
            importlib.import_module("{}.{}".format(module, i.name)), isclass
        ):
            if not isclass(mbr[1]):
                continue

            if issubclass(mbr[1], base_class):
                classes[mbr[0].lower()] = mbr[1]

    return classes
