from enum import Enum, EnumMeta
import asyncio
import asyncssh

EXCEPTIONS_CONNECTION_ERROR = (
    asyncssh.misc.DisconnectError,
    asyncssh.misc.ChannelOpenError,
    asyncio.TimeoutError
)

EXCEPTIONS_AUTHN_ERROR = (
    asyncssh.misc.PasswordChangeRequired,
    asyncssh.misc.ProtocolError
)


class PrettyPrintEnum(EnumMeta):
    '''Meta class used to pretty print an enum'''
    def __str__(cls):
        lines = [f"The {cls.__name__} values are:"]
        # pylint: disable=not-an-iterable
        for member in cls:
            lines.append(f"{member.value} {member.name}")
        return '\n'.join(lines)


class ServiceStatus(Enum, metaclass=PrettyPrintEnum):
    '''Enum representing return status of sq-poller services'''
    OK = 0
    COMMAND_TIMEOUT = 1
    COMMAND_ERROR = 2
    AUTHN_ERROR = 3
    AUTHZ_ERROR = 4
    CONNECTION = 5
    UNDEFINED_SERVICE = 6
    EMPTY_RESPONSE = 7
    UNKNOWN = -1
