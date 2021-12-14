from typing import Dict, List
from suzieq.shared.sq_plugin import SqPlugin


class ControllerPlugin(SqPlugin):
    """Base class for all controller plugins

    Args:
        SqPlugin ([type]): [description]
    """

    @classmethod
    def init_plugins(cls, plugin_conf: dict) -> List[Dict]:
        """Initialize the list of plugins starting from the configuration

        Args:
            plugin_conf (dict): plugin configuration

        Returns:
            List[Dict]: list of generated plugins
        """

        plugin_classes = cls.get_plugins()
        ptype = plugin_conf.get(
            "type")
        if not ptype:
            raise ValueError(
                "generate function espects the plugin type")

        if ptype not in plugin_classes:
            raise RuntimeError(
                f"Unknown plugin called {ptype}"
            )

        return [plugin_classes[ptype](plugin_conf)]
