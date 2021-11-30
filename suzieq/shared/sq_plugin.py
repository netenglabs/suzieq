"""
This module contains all the common logic of
the Suzieq plugins
"""

from importlib import import_module
from importlib.util import find_spec
from inspect import getmembers, getmro, isclass
from pkgutil import iter_modules
from typing import Dict, Type


# pylint: disable=too-few-public-methods
class SqPlugin:
    """SqPlugin is the base common class inherited by all the
    Suzieq plugins
    """

    def __init__(self) -> None:
        pass

    @classmethod
    def get_plugins(cls,
                    search_pkg: str,
                    transitive=False) -> Dict[str, Type]:
        """Discover all the plugins in the search_pkg package, inheriting
        the current base class.

        Args:
            search_pkg (str): The package where to look for the plugins.
                Note that if the specified package contains other packages,
                the function will scan only their content, without accessing
                to other nested packages and ignoring all the files inside
                search_pkg.
            transitive (bool, optional): If False returns a plugin only if
                it is a direct descendant of the base class.
                Defaults to False.

        Returns:
            Dict[str, Type]: a dictionary containing all
                the descendants of the base class in the search_pkg,
                with format {'module name': PluginClass}
        """
        classes = {}

        # Collect the list of packages where to search
        search_path = search_pkg.replace('.', '/')
        packages = [f'{search_pkg}.{m.name}'
                    for m in iter_modules([search_path])
                    if m.ispkg]
        if not packages:
            packages.append(search_pkg)

        for pkg in packages:
            pspec = find_spec(pkg)
            if pspec and pspec.loader:
                mfound = [x.split('.')[0] for x in pspec.loader.contents()
                          if not x.startswith('_')]
                for minfo in mfound:
                    use_name = minfo.split('.')[0]
                    mname = f'{pkg}.{use_name}'
                    mod = import_module(mname)
                    for mbr in getmembers(mod, isclass):
                        if (mbr[1].__module__ == mname
                           and (transitive or getmro(mbr[1])[1] == cls)
                           and issubclass(mbr[1], cls)
                           and mbr[1] != cls):
                            classes[use_name] = mbr[1]

        return classes
