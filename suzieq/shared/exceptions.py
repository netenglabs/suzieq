"""List of Exceptions specific to Suzieq, across all the modules."""


class SqCoalescerCriticalError(Exception):
    """Raised when a critical error occuur inside the coalescer"""


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


class SqVersConversionError(SqCoalescerCriticalError):
    """Raised if there is an error while converting the data"""


class SqPollerConfError(Exception):
    """Invalid poller configuration error."""


class InventorySourceError(Exception):
    """Unable to read or parse the inventory source."""


class PollingError(Exception):
    """Exception raised every time there is an error while polling"""


class SensitiveLoadError(Exception):
    """Sensitive informarmation isn't loaded correctly"""


class SqBrokenFilesError(Exception):
    """Raise when there are broken files and it is not possible to return a
    coherent result."""
