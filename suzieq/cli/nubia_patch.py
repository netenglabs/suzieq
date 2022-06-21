from collections import namedtuple, OrderedDict
from inspect import isclass

from nubia.internal.helpers import (
    get_arg_spec,
    function_to_str,
    transform_name,
)


Argument = namedtuple(
    "Argument",
    "arg description type "
    "default_value_set default_value "
    "name extra_names positional choices",
)

Command = namedtuple("Command", "name help aliases exclusive_arguments")

FunctionInspection = namedtuple(
    "FunctionInspection", "arguments command subcommands"
)
_ArgDecoratorSpec = namedtuple(
    "_ArgDecoratorSpec", "arg name aliases description positional choices"
)

# pylint: disable=redefined-builtin


def argument(
    arg,
    type=None,
    description=None,
    name=None,
    aliases=None,
    positional=False,
    choices=None,
):
    """
    Annotation decorator to specify metadata for an argument

    Check the module documentation for more info and tests.py in this module
    for usage examples
    """

    def decorator(function):
        # Following makes interactive really slow. (T20898480)
        # This should be revisited in T20899641
        #  if (description is not None and \
        #       arg is not None and type is not None):
        #      append_doc(function, arg, type, description)

        fn_specs = get_arg_spec(function)
        args = fn_specs.args or []
        if arg not in args and not fn_specs.varkw:
            raise NameError(
                "Argument {} does not exist in function {}".format(
                    arg, function_to_str(function)
                )
            )

        # init structures to store decorator data if not present
        _init_attr(function, "__annotations__", OrderedDict())
        _init_attr(function, "__arguments_decorator_specs", {})

        # Check if there is a conflict in type annotations
        current_type = function.__annotations__.get(arg)
        if current_type and type and current_type != type:
            raise TypeError(
                "Argument {} in {} is both specified as {} "
                "and {}".format(
                    arg, function_to_str(function), current_type, type
                )
            )

        # if arg in function.__arguments_decorator_specs:
        #   raise ValueError(
        #     "@argument decorator was applied twice "
        #     "for the same argument {} on function {}".format(arg, function)
        #   )

        if positional and aliases:
            msg = ("Aliases are not yet supported for positional arguments"
                   "@ {}".format(arg))
            raise ValueError(msg)

        # reject positional=True if we are applied over a class
        if isclass(function) and positional:
            raise ValueError(
                "Cannot set positional arguments for super commands"
            )

        # We use __annotations__ to allow the usage of python 3 typing
        function.__annotations__.setdefault(arg, type)

        function.__arguments_decorator_specs[arg] = _ArgDecoratorSpec(
            arg=arg,
            description=description,
            name=name or transform_name(arg),
            aliases=aliases or [],
            positional=positional,
            choices=choices or [],
        )

        return function

    return decorator


def _init_attr(obj, attribute, default_value):
    if not hasattr(obj, attribute):
        setattr(obj, attribute, default_value)
