import abc
import collections
from ipaddress import IPv4Network, IPv6Network, ip_network
from ipaddress import IPv4Address, IPv6Address

import six
import numpy as np
import pandas as pd
from pandas.api.extensions import ExtensionDtype, take
from pandas.api.types import is_list_like

from cyberpandas._accessor import (DelegatedMethod, DelegatedProperty,
                                   delegated_method)
from cyberpandas.base import NumPyBackedExtensionArrayMixin

# -----------------------------------------------------------------------------
# Extension Type
# -----------------------------------------------------------------------------


@six.add_metaclass(abc.ABCMeta)
class IPv4v6Network(object):
    """Metaclass providing a common base class for the two scalar IP types."""
    pass


IPv4v6Network.register(IPv4Network)
IPv4v6Network.register(IPv6Network)


@pd.api.extensions.register_extension_dtype
class IPNetworkType(ExtensionDtype):
    name = 'ipnetwork'
    type = IPv4v6Network
    kind = 'O'
    na_value = ip_network("0.0.0.0", strict=False)

    @classmethod
    def construct_from_string(cls, string):
        if string == cls.name:
            return cls()
        else:
            raise TypeError("Cannot construct a '{}' from "
                            "'{}'".format(cls, string))

    @classmethod
    def construct_array_type(cls):
        return IPNetworkArray


# -----------------------------------------------------------------------------
# Extension Container
# -----------------------------------------------------------------------------


class IPNetworkArray(NumPyBackedExtensionArrayMixin):
    """Holder for IP Networks.

    IPNetworkArray is a container for IPv4 or IPv6 networks. It satisfies '
    pandas' extension array interface, and so can be stored inside
    :class:`pandas.Series` and :class:`pandas.DataFrame`.

    See :ref:`usage` for more.
    """
    # We store everything as ipaddress' IPv4Network or IPv6Network.
    # An alternative is to replicate the implementation of IPxNetwork in
    # ipaddress. The latter approach *may* provide some efficiency in being
    # able to do array operations via numpy rather than as list comprehensions.
    __array_priority__ = 1000
    _dtype = IPNetworkType()
    _itemsize = 56
    ndim = 1
    can_hold_na = True

    def __init__(self, values, dtype=None, copy=False):

        values = _to_ipnetwork_array(values)  # TODO: avoid potential copy
        # TODO: dtype?
        if copy:
            values = values.copy()
        self.data = values

    @classmethod
    def _from_ndarray(cls, data, copy=False):
        """Zero-copy construction of an IPNetworkArray from an ndarray.

        Parameters
        ----------
        data : ndarray
            This should have IPNetworkType dtype
        copy : bool, default False
            Whether to copy the data.

        Returns
        -------
        IPNetworkArray
        """
        if copy:
            data = data.copy()
        new = IPNetworkArray([])
        new.data = data
        return new

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------
    @property
    def na_value(self):
        """The missing value sentinal for IP Neworks.

        The address ``'0.0.0.0/32'`` is used.

        Examples
        --------
        >>> IPNetworkArray([]).na_value
        IPv4Network('0.0.0.0/32')
        """
        return self.dtype.na_value

    def take(self, indices, allow_fill=False, fill_value=None):
        '''This is a direct copy of the code from pandas documentation'''
        # If the ExtensionArray is backed by an ndarray, then
        # just pass that here instead of coercing to object.
        data = self.astype(object)

        if allow_fill and fill_value is None:
            fill_value = self.dtype.na_value

        # fill value should always be translated from the scalar
        # type for the array, to the physical storage type for
        # the data, before passing to take.

        result = take(data, indices, fill_value=fill_value,
                      allow_fill=allow_fill)
        return self._from_sequence(result, dtype=self.dtype)

    # -------------------------------------------------------------------------
    # Interfaces
    # -------------------------------------------------------------------------

    def __repr__(self):
        formatted = [x.__repr__() for x in self.data]
        return "IPNetworkArray({!r})".format(formatted)

    def _format_values(self):
        return [x.__repr__() for x in self.data]

    @staticmethod
    def _box_scalar(scalar):
        return NotImplemented

    @property
    def _parser(self):
        return to_ipnetwork

    def __setitem__(self, key, value):
        value = to_ipnetwork(value).data
        self.data[key] = value

    def __iter__(self):
        return iter(self.to_pyipnetwork())

    # ------------------------------------------------------------------------
    # Serializaiton / Export
    # ------------------------------------------------------------------------

    def to_pyipnetwork(self):
        """Convert the array to a list of scalar IP Network objects.

        Returns
        -------
        networks : List
            Each element of the list will be an :class:`ipaddress.IPv4Network`
            or :class:`ipaddress.IPv6Network`, depending on the size of that
            element.

        Examples
        ---------
        >>> IPNetworkArray(['192.168.1.1/24', '2001:db8::1000/128']).to_pyipaddress()
        [IPv4Network('192.168.1.0/24'), IPv6Network('2001:db8::1000/128')]
        """
        return [x for x in self.data]

    def astype(self, dtype, copy=True):
        if isinstance(dtype, IPNetworkType):
            if copy:
                self = self.copy()
            return self
        return super(IPNetworkArray, self).astype(dtype)

    # ------------------------------------------------------------------------
    # Ops
    # ------------------------------------------------------------------------

    def __eq__(self, other):
        if isinstance(other, str):
            pyips = self.to_pyipnetwork()
            try:
                match = ip_network(other, strict=False)
            except:
                return NotImplemented
            return np.array([ip == match for ip in pyips])
        elif isinstance(other, IPNetworkArray):
            return self.data == other.data
        else:
            return NotImplemented

    def __lt__(self, other):
        # TDOO: scalar ipaddress
        if not isinstance(other, IPNetworkArray):
            return NotImplemented
        return (self.data < other.data)

    def __le__(self, other):
        if not isinstance(other, IPNetworkArray):
            return NotImplemented
        return (self.data <= other.data)

    def __gt__(self, other):
        if not isinstance(other, IPNetworkArray):
            return NotImplemented
        return (self.data > other.data)

    def __ge__(self, other):
        if not isinstance(other, IPNetworkArray):
            return NotImplemented
        return (self.data >= other.data)

    def equals(self, other):
        if not isinstance(other, IPNetworkArray):
            raise TypeError("Cannot compare 'IPNetworkArray' "
                            "to type '{}'".format(type(other)))
        # TODO: missing
        return (self.data == other.data).all()

    def value_counts(self, sort=True, ascending=False, normalize=False,
                     bins=None, dropna=True):

        from pandas.core.algorithms import value_counts

        pyips = self.to_pyipnetwork()
        return value_counts(pyips, sort, ascending, normalize, bins, dropna)

    def _reduce(self, name, **kwargs):
        if name == 'max':
            return self._max(**kwargs)
        elif name == 'min':
            return self._min(**kwargs)
        return NotImplemented

    def _max(self, **kwargs):
        pyips = self.to_pyipnetwork()
        skipna = kwargs.get('skipna', True)
        result = None

        for ip in pyips:
            if (skipna and ip != self.na_value) or not skipna:
                if not result:
                    result = ip
                    continue
                if ip > result:
                    result = ip

        return result

    def _min(self, **kwargs):
        pyips = self.to_pyipnetwork()
        skipna = kwargs.get('skipna', True)
        result = None

        for ip in pyips:
            if (skipna and ip != self.na_value) or not skipna:
                if not result:
                    result = ip
                    continue
                if ip < result:
                    result = ip

        return result

    def isna(self):
        """Indicator for whether each element is missing.

        The IPNetwork '0.0.0.0/32' is used to indicate missing values.

        Examples
        --------
        >>> IPNetworkArray(['0.0.0.0/32', '192.168.1.1/24']).isna()
        array([ True, False])
        """
        ips = self.data
        return (ips == ip_network('0.0.0.0', strict=False))

    def isin(self, other):
        """Check whether elements of `self` are in `other`.

        Comparison is done elementwise.

        Parameters
        ----------
        other : str or list of str or IPNetworkArray
            For ``str`` `other`, the argument is attempted to
            be converted to an :class:`ipaddress.IPv4Network` or
            a :class:`ipaddress.IPv6Network`. If the conversion fails, 
            a TypeError is raised.

            For a sequence of strings, the same conversion is attempted.
            You should not mix networks with addresses.

            Finally, other may be an ``IPNetworkArray`` of networks to compare.

        Returns
        -------
        contained : ndarray
            A 1-D boolean ndarray with the same length as self.

        Examples
        --------
        Comparison to a single network

        >>> s = IPNetworkArray(['192.168.1.0/32', '10.1.1.1/32'])
        >>> s.isin('192.168.1.0/24')
        array([ True, False])

        Comparison to many networks
        >>> s.isin(['192.168.1.0/24', '192.168.2.0/24'])
        array([ True, False])
        """
        from pandas.core.algorithms import isin

        if not is_list_like(other):
            other = [other]
        if isinstance(other, IPNetworkArray):
            to_match = other
        else:
            to_match = [ip_network(x, strict=False) for x in other]

        mask = np.zeros(len(self), dtype='bool')
        mask |= isin(self, to_match)
        return mask

    def subnet_of(self, addr):
        """Returns true if addr is in subnet; includes default route"""
        if isinstance(addr, str):
            ips = self.data
            match = ip_network(addr, strict=False)
            if match._version == 4:
                return np.array([match.subnet_of(ip)
                                 if ip._version == 4 else False
                                 for ip in ips])
            else:
                return np.array([match.subnet_of(ip)
                                 if ip._version == 6 else False
                                 for ip in ips])

        return NotImplemented

    # ------------------------------------------------------------------------
    # IP Specific
    # ------------------------------------------------------------------------

    @property
    def is_ipv4(self):
        """Indicator for whether each address fits in the IPv4 space."""
        # TODO: NA should be NA
        pyips = self.to_pyipnetwork()
        return np.array([ip._version == 4 for ip in pyips])

    @property
    def is_ipv6(self):
        """Indicator for whether each address requires IPv6."""
        pyips = self.to_pyipnetwork()
        return np.array([ip._version == 6 for ip in pyips])

    @property
    def version(self):
        """IP version (4 or 6)."""
        return np.where(self.is_ipv4, 4, 6)

    @property
    def is_multicast(self):
        """Indiciator for whether each address is multicast."""
        pyips = self.to_pyipnetwork()
        return np.array([ip.is_multicast for ip in pyips])

    @property
    def is_default(self):
        """Indiciator for whether each prefix is the default route."""
        pyips = self.to_pyipnetwork()
        dflt = ip_network('0.0.0.0/0')
        return np.array([ip == dflt for ip in pyips])

    @property
    def is_private(self):
        """Indiciator for whether each address is private."""
        pyips = self.to_pyipnetwork()
        return np.array([ip.is_private for ip in pyips])

    @property
    def is_global(self):
        """Indiciator for whether each address is global."""
        pyips = self.to_pyipnetwork()
        return np.array([ip.is_global for ip in pyips])

    @property
    def is_unspecified(self):
        """Indiciator for whether each address is unspecified."""
        pyips = self.to_pyipnetwork()
        return np.array([ip.is_unspecified for ip in pyips])

    @property
    def is_reserved(self):
        """Indiciator for whether each address is reserved."""
        pyips = self.to_pyipnetwork()
        return np.array([ip.is_reserved for ip in pyips])

    @property
    def is_loopback(self):
        """Indiciator for whether each address is loopback."""
        pyips = self.to_pyipnetwork()
        return np.array([ip.is_loopback for ip in pyips])

    @property
    def is_link_local(self):
        """Indiciator for whether each address is link local."""
        pyips = self.to_pyipnetwork()
        return np.array([ip.is_link_local for ip in pyips])

    @property
    def packed(self):
        """Bytestring of the IP addresses

        Each address takes 16 bytes. IPv4 addresses are prefixed
        by zeros.
        """
        # TODO: I wonder if that should be post-fixed by 0s.
        return self.data.tobytes()

    @property
    def prefixlen(self):
        """Return the prefixlen of each prefix in the array"""
        pyips = self.to_pyipnetwork()
        return np.array([ip.prefixlen for ip in pyips])

# -----------------------------------------------------------------------------
# Accessor
# -----------------------------------------------------------------------------


@pd.api.extensions.register_series_accessor("ipnet")
class IPNetAccessor:

    is_ipv4 = DelegatedProperty("is_ipv4")
    is_ipv6 = DelegatedProperty("is_ipv6")
    version = DelegatedProperty("version")
    is_multicast = DelegatedProperty("is_multicast")
    is_private = DelegatedProperty("is_private")
    is_global = DelegatedProperty("is_global")
    is_unspecified = DelegatedProperty("is_unspecified")
    is_reserved = DelegatedProperty("is_reserved")
    is_loopback = DelegatedProperty("is_loopback")
    is_link_local = DelegatedProperty("is_link_local")
    is_default = DelegatedProperty("is_default")
    prefixlen = DelegatedProperty("prefixlen")

    isna = DelegatedMethod("isna")

    def __init__(self, obj):
        self._validate(obj)
        self._data = obj.values
        self._index = obj.index
        self._name = obj.name

    @staticmethod
    def _validate(obj):
        if not is_ipnetwork_type(obj):
            raise AttributeError("Cannot use 'ipnet' accessor on objects of "
                                 "dtype '{}'.".format(obj.dtype))

    def isin(self, other):
        return delegated_method(self._data.isin, self._index,
                                self._name, other)

    def subnet_of(self, other):
        return delegated_method(self._data.subnet_of, self._index,
                                self._name, other)

def is_ipnetwork_type(obj):

    t = getattr(obj, 'dtype', obj)
    try:
        return isinstance(t, IPNetworkType) or issubclass(t, IPNetworkType)
    except Exception:
        return False


def _to_ipnetwork_array(values):
    from suzieq.ipnetwork_array import IPNetworkType, IPNetworkArray

    if isinstance(values, IPNetworkArray):
        return values.data

    if (isinstance(values, np.ndarray) and
            values.ndim == 1 and
            np.issubdtype(values.dtype, np.string_)):
        values = np.asarray(values, dtype=IPNetworkType)
    else:
        values = [ip_network(x, strict=False) for x in values]

    return np.atleast_1d(np.asarray(values, dtype=IPNetworkType))


def to_ipnetwork(values):
    """Convert values to IPNetworkArray

    Parameters
    ----------
    values : int, str, bytes, or sequence of those

    Returns
    -------
    addresses : IPNetworkArray

    Examples
    --------
    Parse strings
    >>> to_ipnetwork(['192.168.1.1/24',
    ...               '2001:0db8:85a3:0000:0000:8a2e:0370:7334/128'])
    <IPNetworkArray([IPv4Network('192.168.1.1'), IPv6Network('0:8a2e:370:7334:2001:db8:85a3:0')])>
    """
    from suzieq.ipnetwork_array import IPNetworkArray

    if not is_list_like(values):
        values = [values]

    return IPNetworkArray(_to_ipnetwork_array(values))


