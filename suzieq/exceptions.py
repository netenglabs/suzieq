# List of Exceptions specific to Suzieq, across all the modules


class NoLLdpError(Exception):
    pass


class EmptyDataframeError(Exception):
    pass


class PathLoopError(Exception):
    pass


class DBReadError(Exception):
    pass


class DBNotFoundError(Exception):
    pass


class UserQueryError(Exception):
    pass
