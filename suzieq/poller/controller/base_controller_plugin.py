from typing import Dict, List
from suzieq.shared.exceptions import SqPollerConfError
from suzieq.shared.sq_plugin import SqPlugin


class ControllerPlugin(SqPlugin):
    """Base class for all controller plugins

    Args:
        SqPlugin ([type]): [description]
    """

    @classmethod
    def init_plugins(cls, plugin_conf: Dict) -> List[Dict]:
        """Instantiate one or more instances of the current class according
        to the given configuration

        Args:
            plugin_conf (dict): plugin configuration

        Returns:
            List[Dict]: list of generated plugins
        """

        if plugin_conf is None:
            raise RuntimeError('Plugin configuration cannot be None')

        ptype = plugin_conf.get("type")
        if not ptype:
            raise SqPollerConfError('No default type provided')

        controller_class = cls.get_plugins(plugin_name=ptype)

        if not controller_class:
            raise SqPollerConfError(f"Unknown plugin called {ptype}")

        return [controller_class[ptype](plugin_conf)]
