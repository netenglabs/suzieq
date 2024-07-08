# List of normalized error codes used in the poller

from enum import IntEnum

# Ensure you never copy backwards compat values


class SqPollerStatusCode(IntEnum):
    '''SuzieQ Poller Status Codes and their strings'''

    OK = 0, 'OK'
    HTTP_OK = 200, 'OK'
    PERMISSION_DENIED = 1001, 'Permission Denied'
    UNAUTHORIZED = 1002, 'Unauthorized'
    LOGIN_FAIL = 1003, 'Login Failed'
    PRIV_ESC_FAIL = 1004, 'Privilege Escalation Failed'
    NON_FINAL_FAILURES = 1005, 'Dummy to mark boundary, never set'
    CMD_NOT_FOUND = 2006, 'Command Not Found'
    EMPTY_OUTPUT = 2007, 'Output Empty'
    INCOMPLETE_CMD = 2008, 'Command Incomplete'
    TIMEOUT = 2009, 'Command Timeout'
    DISABLED_FEATURE = 2010, 'Feature Disabled'
    CONNECT_FAIL = 2011, 'Connect Failed'
    PARSING_ERROR = 2012, 'Parsing Failed'
    UNSUPPORTED_SVC = 2013, 'Service Not Supported'
    UNSUPPORTED_CMD = 2014, 'Command Not Supported'
    NO_RT_TO_HOST = 2015, 'No Route to Host'
    VAR_NOT_SET = 2016, 'Variable Not Set'
    WAITING_FOR_VAR = 2017, 'Variable Waiting'
    ERR_OUTPUT = 2018, 'Command Failed'
    GEN_CLS_FAIL = 2019, 'Linux Cmd Failed'
    UNREACH_NET = 2020, 'Network Unreachable'
    NO_SVC_DEF = 2021, 'Service Not Defined'
    UNKNOWN_FAILURE = 2022, 'Unknown Failure'
    CONN_REFUSED = 2023, 'Connection Refused'
    UNEXPECTED_DISCONNECT = 2024, 'Unexpected Disconnect'

    # Everything below this is for backward compat
    LINUX_OLD_CMD_NOT_FOUND = 1, 'Command Not Found'
    NXOS_CMD_NOT_FOUND = 16, 'Command Not Found'
    NXOS_YACNF = 20, 'Command Not Found'
    LINUX_CMD_NOT_FOUND = 127, 'Command Not Found'
    HTTP_EMPTY_OUTPUT = 204, 'Empty Output'
    OLD_EMPTY_OUTPUT = 244, 'Empty Output'
    HTTP_INCOMPLETE_CMD = 400, 'Incomplete Command'
    HTTP_LOGIN_FAIL = 401, 'Login Failed'
    HTTP_BAD_CMD = 404, 'Command Not Found'
    HTTP_YAIC = 405, 'Incomplete Command'
    HTTP_TIMEOUT = 408, 'Timeout'
    OLD_FEATURE_DISABLED = 418, 'Feature Disabled'
    OLD_PARSING_ERROR = 502, 'Parsing Error'
    OLD_PRIV_ESC_FAIL = -1, 'Privilege Escalation Failed'

    def __new__(cls, code: int, errstr: str):
        obj = int.__new__(cls, code)
        obj._value_ = code
        obj.errstr = errstr

        return obj

    def is_error_code_final(self):
        '''is the node in stopped state'''
        return (self.value < self.NON_FINAL_FAILURES.value)
