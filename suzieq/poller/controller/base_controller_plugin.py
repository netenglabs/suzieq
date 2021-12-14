from typing import Dict, List
from suzieq.shared.sq_plugin import SqPlugin

class ControllerPlugin(SqPlugin):
    """Base class for all controller plugins

    Args:
        SqPlugin ([type]): [description]
    """
    @classmethod
    def generate(plugin_conf: dict) -> List[Dict]:
        """Generate the list of plugins starting from the configuration

        Args:
            plugin_conf (dict): plugin configuration

        Returns:
            List[Dict]: list of generated plugins
        """
        pass
