import importlib
from pkgutil import walk_packages
from inspect import getmembers, isclass
from os.path import dirname, abspath

INVENTORY_PROVIDER_PATH = abspath(dirname(__file__))


def get_classname_from_type(type: str):
    """
    Return the name of a class starting from its type

    example:
    plugin_type = chunker -> class = Chunker
    """
    if len(type) > 1:
        return type[0].upper() + type[1:]


def obtain_module_path(abs_path: str):
    abs_path = abs_path.replace("//", "/")
    if "suzieq/suzieq" not in abs_path:
        raise ValueError("You must pass the absolute path to obtain "
                         "the module path")
    abs_path = abs_path[
        abs_path.find("suzieq")+7:
    ]
    return abs_path.replace("/", ".")


def get_class_by_path(
    search_path: str,
    base_class_path: str,
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

    base_class_module = obtain_module_path(base_class_path)

    for m in walk_packages([base_class_path]):
        for bmbr in getmembers(
            importlib.import_module(f"{base_class_module}.{m.name}"), isclass
        ):
            if bmbr[0] == base_class_name:
                base_class = bmbr[1]
                break

    if not base_class:
        raise RuntimeError(
            "Base class {} not found at {}"
            .format(base_class_name, base_class_module)
        )

    search_class_module = obtain_module_path(search_path)
    for m in walk_packages([search_path]):
        for mbr in getmembers(
            importlib.import_module(f"{search_class_module}.{m.name}"), isclass
        ):
            if issubclass(mbr[1], base_class):
                classes[mbr[0].lower()] = mbr[1]
    return classes
