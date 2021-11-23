"""List of Exceptions specific to Suzieq, across all the modules."""


class NoLLdpError(Exception):
    """No LLDP error."""


class EmptyDataframeError(Exception):
    """Empty dataframe error."""


class PathLoopError(Exception):
    """Path loop error."""


class DBReadError(Exception):
    """Database read error."""


class DBNotFoundError(Exception):
    """Database not found error."""


class UserQueryError(Exception):
    """User query error."""


class UnknownDevtypeError(Exception):
    """Unknown dev type error."""
