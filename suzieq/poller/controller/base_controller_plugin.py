from copy import deepcopy
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, model_validator
from suzieq.shared.exceptions import SqPollerConfError
from suzieq.shared.sq_plugin import SqPlugin


def _underscore_to_dash(field_name: str) -> str:
    """Replaces the undescore in the name of the field to a dash
    """
    return field_name.replace('_', '-')


class BasePluginModel(BaseModel):
    """Base model for plugins validation
    """
    model_config = ConfigDict(
        extra='forbid',
        alias_generator=_underscore_to_dash,
    )

    name: str

    @model_validator(mode='before')
    @classmethod
    def check_extra_fields(cls, data):
        """Keep the legacy validation error message for unknown fields."""
        if not isinstance(data, dict):
            return data
        if 'name' not in data:
            return data
        valid_fields = set(cls.model_fields)
        valid_fields.update(
            field.alias for field in cls.model_fields.values()
            if field.alias
        )
        extra_fields = set(data) - valid_fields
        if extra_fields:
            raise ValueError(
                f'{sorted(extra_fields)[0]}: extra fields not permitted')
        return data


class InventoryPluginModel(BasePluginModel):
    """Model for inventory validation
    """
    type: Optional[str] = None


class ControllerPlugin(SqPlugin):
    """Base class for all controller plugins

    Args:
        SqPlugin ([type]): [description]
    """
    # pylint: disable=unused-argument
    def __init__(self, plugin_conf: Dict, validate: bool = True) -> None:
        self._validate = validate

    @classmethod
    def init_plugins(cls, plugin_conf: Dict, validate: bool = False) \
            -> List[Dict]:
        """Instantiate one or more instances of the current class according
        to the given configuration.
        The validation is set to False by default because when the init_plugins
        function is called, the configuration has already been validated.

        Args:
            plugin_conf (dict): plugin configuration
            validate (bool): validate the plugin during initialization
                             Default: False

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

        return [controller_class[ptype](deepcopy(plugin_conf), validate)]

    @classmethod
    def default_type(cls) -> str:
        """Return the default type for a plugin
        """
        raise NotImplementedError

    @classmethod
    def get_data_model(cls) -> BasePluginModel:
        """Return the model used for the data
        """
        raise NotImplementedError
