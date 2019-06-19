import abc
import collections
import ipaddress

import six
import numpy as np
import pandas as pd
from pandas.api.extensions import ExtensionDtype, take
from pandas.api.types import is_list_like

from cyberpandas._accessor import (DelegatedMethod, DelegatedProperty,
                                   delegated_method)
from cyberpandas._utils import combine, pack, unpack
from cyberpandas.base import NumPyBackedExtensionArrayMixin
from cyberpandas.common import _U8_MAX, _IPv4_MAX

# -----------------------------------------------------------------------------
# Extension Type
# -----------------------------------------------------------------------------


@six.add_metaclass(abc.ABCMeta)
class IPv4v6Network(object):
    """Metaclass providing a common base class for the two scalar IP types."""
    pass


IPv4v6Network.register(ipaddress.IPv4Network)
IPv4v6Network.register(ipaddress.IPv6Network)


@pd.api.extensions.register_extension_dtype
class IPNetworkType(ExtensionDtype):
    name = 'ipnetwork'
    type = IPv4v6Network
    kind = 'O'
    _record_type = np.string_
    na_value = ipaddress.ip_network("0.0.0.0", strict=False)

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

    IPArray is a container for IPv4 or IPv6 addresses. It satisfies pandas'
    extension array interface, and so can be stored inside
    :class:`pandas.Series` and :class:`pandas.DataFrame`.

    See :ref:`usage` for more.
    """
    # A note on the internal data layout. IPv6 addresses require 128 bits,
    # which is more than a uint64 can store. So we use a NumPy structured array
    # with two fields, 'hi', 'lo' to store the data. Each field is a uint64.
    # The 'hi' field contains upper 64 bits. The think this is correct since
    # all IP traffic is big-endian.
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
        """Zero-copy construction of an IPArray from an ndarray.

        Parameters
        ----------
        data : ndarray
            This should have IPType._record_type dtype
        copy : bool, default False
            Whether to copy the data.

        Returns
        -------
        ExtensionArray
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

        The address ``'0.0.0.0'`` is used.

        Examples
        --------
        >>> IPArray([]).na_value
        IPv4Address('0.0.0.0')
        """
        return self.dtype.na_value

    def take(self, indices, allow_fill=False, fill_value=None):
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
        return ipaddress.ip_network(combine(*scalar), strict=False)

    @property
    def _parser(self):
        raise NotImplementedError

    def __setitem__(self, key, value):
        raise NotImplementedError

    def __iter__(self):
        return iter(self.to_pyipnetwork())

    # ------------------------------------------------------------------------
    # Serializaiton / Export
    # ------------------------------------------------------------------------

    def to_pyipnetwork(self):
        """Convert the array to a list of scalar IP Network objects.

        Returns
        -------
        addresses : List
            Each element of the list will be an :class:`ipaddress.IPv4Address`
            or :class:`ipaddress.IPv6Address`, depending on the size of that
            element.

        See Also
        --------
        IPArray.to_pyints

        Examples
        ---------
        >>> IPArray(['192.168.1.1', '2001:db8::1000']).to_pyipaddress()
        [IPv4Address('192.168.1.1'), IPv6Address('2001:db8::1000')]
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
        # TDOO: scalar ipaddress
        if not isinstance(other, IPNetworkArray):
            return NotImplemented
        mask = self.isna() | other.isna()
        result = self.data == other.data
        result[mask] = False
        return result

    def __lt__(self, other):
        # TDOO: scalar ipaddress
        return NotImplemented

    def __le__(self, other):
        return NotImplemented

    def __gt__(self, other):
        return NotImplemented

    def __ge__(self, other):
        return NotImplemented

    def equals(self, other):
        if not isinstance(other, IPNetworkArray):
            raise TypeError("Cannot compare 'IPNetworkArray' "
                            "to type '{}'".format(type(other)))
        # TODO: missing
        return (self.data == other.data).all()

    def _values_for_factorize(self):
        return self.astype(object), ipaddress.ip_network('0.0.0.0',
                                                         strict=False)

    def isna(self):
        """Indicator for whether each element is missing.

        The IPNetwork 0 is used to indecate missing values.

        Examples
        --------
        >>> IPArray(['0.0.0.0', '192.168.1.1']).isna()
        array([ True, False])
        """
        ips = self.data
        return (ips == ipaddress.ip_network('0.0.0.0', strict=False))

    def isin(self, other):
        """Check whether elements of `self` are in `other`.

        Comparison is done elementwise.

        Parameters
        ----------
        other : str or sequences
            For ``str`` `other`, the argument is attempted to
            be converted to an :class:`ipaddress.IPv4Network` or
            a :class:`ipaddress.IPv6Network` or an :class:`IPArray`.
            If all those conversions fail, a TypeError is raised.

            For a sequence of strings, the same conversion is attempted.
            You should not mix networks with addresses.

            Finally, other may be an ``IPArray`` of addresses to compare to.

        Returns
        -------
        contained : ndarray
            A 1-D boolean ndarray with the same length as self.

        Examples
        --------
        Comparison to a single network

        >>> s = IPArray(['192.168.1.1', '255.255.255.255'])
        >>> s.isin('192.168.1.0/24')
        array([ True, False])

        Comparison to many networks
        >>> s.isin(['192.168.1.0/24', '192.168.2.0/24'])
        array([ True, False])

        Comparison to many IP Addresses

        >>> s.isin(['192.168.1.1', '192.168.1.2', '255.255.255.1']])
        array([ True, False])
        """
        box = (isinstance(other, str) or
               not isinstance(other, (IPNetworkArray, collections.Sequence)))
        if box:
            other = [other]

        networks = []
        addresses = []

        if not isinstance(other, IPNetworkArray):
            for net in other:
                net = _as_ip_object(net)
                if isinstance(net, (ipaddress.IPv4Network,
                                    ipaddress.IPv6Network)):
                    networks.append(net)
                if isinstance(net, (ipaddress.IPv4Address,
                                    ipaddress.IPv6Address)):
                    addresses.append(ipaddress.IPv6Network(net))
        else:
            addresses = other

        # Flatten all the addresses
        addresses = IPArray(addresses)  # TODO: think about copy=False

        mask = np.zeros(len(self), dtype='bool')
        for network in networks:
            mask |= self._isin_network(network)

        # no... we should flatten this.
        mask |= self._isin_addresses(addresses)
        return mask

    def _isin_network(self, other):
        """Check whether an array of addresses is contained in a network."""
        # A network is bounded below by 'network_address' and
        # above by 'broadcast_address'.
        # IPArray handles comparisons between arrays of addresses, and NumPy
        # handles broadcasting.
        net_lo = type(self)([other.network_address])
        net_hi = type(self)([other.broadcast_address])

        return (net_lo <= self) & (self <= net_hi)

    def _isin_addresses(self, other):
        """Check whether elements of self are present in other."""
        from pandas.core.algorithms import isin
        # TODO(factorize): replace this
        return isin(self, other)

    # ------------------------------------------------------------------------
    # IP Specific
    # ------------------------------------------------------------------------

    @property
    def is_ipv4(self):
        """Indicator for whether each address fits in the IPv4 space."""
        # TODO: NA should be NA
        ips = self.data
        return (ips['hi'] == 0) & (ips['lo'] < _U8_MAX)

    @property
    def is_ipv6(self):
        """Indicator for whether each address requires IPv6."""
        ips = self.data
        return (ips['hi'] > 0) | (ips['lo'] > _U8_MAX)

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
        dflt = ipaddress.ip_network('0.0.0.0/0')
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


def is_ipnetwork_type(obj):

    t = getattr(obj, 'dtype', obj)
    try:
        return isinstance(t, IPNetworkType) or issubclass(t, IPNetworkType)
    except Exception:
        return False


def _to_ipnetwork_array(values):
    from suzieq.ipn_dtype import IPNetworkType, IPNetworkArray

    if isinstance(values, IPNetworkArray):
        return values.data

    if (isinstance(values, np.ndarray) and
            values.ndim == 1 and
            np.issubdtype(values.dtype, np.string_)):
        values = np.asarray(values, dtype=IPNetworkType)
    else:
        values = [ipaddress.ip_network(x, strict=False) for x in values]

    return np.atleast_1d(np.asarray(values, dtype=IPNetworkType))


def to_ipnetwork(values):
    """Convert values to IPNetworkArray

    Parameters
    ----------
    values : int, str, bytes, or sequence of those

    Returns
    -------
    addresses : IPArray

    Examples
    --------
    Parse strings
    >>> to_ipaddress(['192.168.1.1',
    ...               '2001:0db8:85a3:0000:0000:8a2e:0370:7334'])
    <IPArray(['192.168.1.1', '0:8a2e:370:7334:2001:db8:85a3:0'])>

    Or integers
    >>> to_ipaddress([3232235777,
                      42540766452641154071740215577757643572])
    <IPArray(['192.168.1.1', '0:8a2e:370:7334:2001:db8:85a3:0'])>

    Or packed binary representations
    >>> to_ipaddress([b'\xc0\xa8\x01\x01',
                      b' \x01\r\xb8\x85\xa3\x00\x00\x00\x00\x8a.\x03ps4'])
    <IPArray(['192.168.1.1', '0:8a2e:370:7334:2001:db8:85a3:0'])>
    """
    from suzieq.ipn_dtype import IPNetworkArray

    if not is_list_like(values):
        values = [values]

    return IPNetworkArray(_to_ipnetwork_array(values))


