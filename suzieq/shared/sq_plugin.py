"""
This module contains all the common logic of
the Suzieq plugins
"""

from importlib import import_module
from importlib.util import find_spec
from inspect import getmembers, getmro, isclass
from pkgutil import iter_modules
from typing import Dict, Type

from suzieq.shared.utils import get_sq_install_dir


class SqPlugin:
    """SqPlugin is the base common class inherited by all the
    Suzieq plugins
    """

    def __init__(self) -> None:
        pass

    @classmethod
    def get_plugins(cls,
                    plugin_name: str = None,
                    search_pkg: str = None) -> Dict[str, Type]:
        """Discover all the plugins in the search_pkg package, inheriting
        the current base class.

        Args:
            plugin_name (str): The name of a specific plugin to extract
            search_pkg (str): The package where to look for the plugins.
                Note that if the specified package contains other packages,
                the function will scan only their content, without accessing
                to other nested packages and ignoring all the files inside
                search_pkg.

        Returns:
            Dict[str, Type]: a dictionary containing all
                the descendants of the base class in the search_pkg,
                with format {'module name': PluginClass}
        """
        classes = {}

        if not search_pkg:
            search_pkg = '.'.join(cls.__module__.split('.')[:-1])

        # Collect the list of packages where to search
        sq_install_dir = '/'.join(get_sq_install_dir().split('/')[:-1])

        search_path = (f"{sq_install_dir}/{search_pkg.replace('.', '/')}")
        packages = [f'{search_pkg}.{m.name}'
                    for m in iter_modules([search_path])
                    if m.ispkg]
        if not packages:
            packages.append(search_pkg)
            use_pkg_name = False
        else:
            use_pkg_name = True

        for pkg in packages:
            found_plugin = False
            if use_pkg_name:
                use_name = pkg.split('.')[-1]
            pspec = find_spec(pkg)
            if pspec and pspec.loader:
                try:
                    mfound = [x.split('.')[0] for x in pspec.loader.contents()
                              if not x.startswith('_') and x.endswith(".py")]
                except Exception:  # pylint: disable=broad-except
                    mfound = []
                for minfo in mfound:
                    if not use_pkg_name:
                        use_name = minfo.split('.')[0]
                        mname = f'{pkg}.{use_name}'
                    else:
                        mname = f'{pkg}.{minfo}'
                    if plugin_name and plugin_name != use_name:
                        continue
                    mod = import_module(mname)
                    for mbr in getmembers(mod, isclass):
                        if (mbr[1].__module__ == mname
                           and getmro(mbr[1])[1] == cls
                           and issubclass(mbr[1], cls)
                           and mbr[1] != cls):
                            classes[use_name] = mbr[1]
                            found_plugin = True
            if plugin_name and found_plugin:
                break

        return classes
