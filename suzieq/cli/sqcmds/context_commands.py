import typing
from nubia import command, argument, context


@command("set")
@argument("namespace", description="namespace to qualify selection")
@argument("hostname", description="Name of host to qualify selection")
@argument(
    "start_time", description="Start of time window in YYYY-MM-dd HH:mm:SS format"
)
@argument("end_time", description="End of time window in YYYY-MM-dd HH:mm:SS format")
@argument("pager", description="Enable pagination prompt on longer outputs",
          choices=['on', 'off'])
@argument(
    "engine",
    choices=["pandas"],
    description="Use Pandas for non-SQL commands",
)
def set_ctxt(
        pager: str = 'on',
        hostname: typing.List[str] = [],
        start_time: str = "",
        end_time: str = "",
        namespace: typing.List[str] = [],
        engine: str = "",
):
    """set certain contexts for subsequent commands. Cmd is additive"""
    plugin_ctx = context.get_context()

    if namespace:
        plugin_ctx.namespace = namespace

    if hostname:
        plugin_ctx.hostname = hostname

    if start_time:
        plugin_ctx.start_time = start_time

    if end_time:
        plugin_ctx.end_time = end_time

    if engine:
        plugin_ctx.change_engine(engine)

    if pager == 'on':
        plugin_ctx.pager = True


@command("clear")
@argument("namespace", description="namespace to qualify selection")
@argument("hostname", description="Name of host to qualify selection")
@argument(
    "start_time", description="Start of time window in YYYY-MM-dd HH:mm:SS format"
)
@argument("end_time", description="End of time window in YYYY-MM-dd HH:mm:SS format")
@argument("pager", description="End of time window in YYYY-MM-dd HH:mm:SS format")
def clear_ctxt(
        pager: str = 'off',
        hostname: str = "",
        start_time: str = "",
        end_time: str = "",
        namespace: str= "",
):
    """clear certain contexts for subsequent commands. Cmd is additive"""
    plugin_ctx = context.get_context()

    if namespace:
        plugin_ctx.namespace = []

    if hostname:
        plugin_ctx.hostname = []

    if start_time:
        plugin_ctx.start_time = ""

    if end_time:
        plugin_ctx.end_time = ""

    if pager:
        plugin_ctx.pager = False
