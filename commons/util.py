"""
util.py

Utilities and helper functions that don't require mido

"""
import sys
import weakref
import itertools
import collections

# SysEx Manufacturer ID
YAMAHA = 0x43


# eprint
def eprint(*args, **kwargs):
    """Print to stderr."""
    print(*args, file=sys.stderr, **kwargs)


# slicing and iteration
def slicebyn(obj, n, end=None):
    """
    Iterator over n-length slices of obj from the range 0 to end.
    end defaults to len(obj).
    """
    if end is None:
        end = len(obj)
    return (obj[i:i+n] for i in range(0, end, n))


def not_none_get(value, not_none):
    """Return value, or not_none if value is None"""
    if value is None:
        return not_none
    else:
        return value


# byte helpers
def assert_low(byte):
    """Raise ValueError if byte > 127"""
    if byte > 0x7F:
        raise ValueError("Byte value out of range: {}".format(byte))


# bitarray helpers
def boolean_bitarray_get(integer, index):
    """The index-th-lowest bit of the integer, as a boolean."""
    return bool((integer >> index) & 0x01)


def boolean_bitarray_tuple(integer, length=8):
    """
    Unpack an integer into a tuple of boolean values, LSB first.
    Uses the lowest bits up to length.
    Raises ValueError if any higher bits are set to 1
    """
    if integer >= (1 << length):
        raise ValueError("Some bits are too high: {}".format(integer))
    return tuple(boolean_bitarray_get(integer, i) for i in range(length))


# yamaha seven byte packing
def seven_byte_length(value):
    """
    Returns the minimum number of bytes required to represent the integer
    if we can use seven bits per byte.
    Positive integers only, please!
    """
    q, rem = divmod(value.bit_length(), 7)
    if rem or not q:
        # (the not q is in case value is 0, we can't have 0 bytes)
        q += 1
    return q


def pack_seven(value, length=None):
    """
    Packs a positive integer value into the seven-bit representation used
    in the sysex message data.
    """
    if value < 0:
        raise ValueError("Value is negative: {}".format(value))
    minlen = seven_byte_length(value)
    if length is None:
        length = minlen
    else:
        # if 2**(7*length) < value...
        if minlen > length:
            raise ValueError("Length too short to fit value")
    dest = bytearray(length)
    for i in range(minlen):
        dest[i] = (value & 0x7F)
        value >>= 7
    return bytes(reversed(dest))


# yamaha seven-byte unpacking & reconsitution
def unpack_seven(inbytes):
    """
    Reconstruct a number from the seven-bit representation used in
    the SysEx message data.
    Takes a bytes-like object, where each byte is seven bits of the number
    (big-endian byte order)
    Each byte must have its high bit zero, or else ValueError is raised.
    """
    value = 0
    for b in inbytes:
        assert_low(b)
        value = (value << 7) | b
    return value


def reconstitute(inbytes):
    """
    Unpack a sequence of eight bytes into a bytearray of seven bytes
    where the highest bit of each byte is determined by the eighth byte,
    that is, unpack eight bytes of the bulk dump payload data
    """
    if len(inbytes) != 8:
        raise ValueError("There must be eight bytes!")
    dest = bytearray(7)
    lastbyte = inbytes[7]
    assert_low(lastbyte)
    for i in range(7):
        byte = inbytes[i]
        assert_low(byte)
        highbit = (lastbyte << (i+1)) & 0x80
        dest[i] = byte | highbit
    return dest


def reconstitute_all(inbytes):
    """
    Unpack a sequence with a length a multiple of eight using the
    reconstitute function. Returns a bytes object.
    """
    if len(inbytes) % 8 != 0:
        raise ValueError("There must be a multiple of eight bytes!")
    # would a memoryview object instead of a slice would be better here?
    return b''.join(reconstitute(x) for x in slicebyn(inbytes, 8))


# midi number helper functions
def unpack_variable_length(inbytes, limit=True):
    """
    Reconstruct a number from the variable-length representation used
    in Standard MIDI files. This version only accepts just the entire sequence
    (that is, last byte must have high bit 0, all other bytes must have
    high bit 1).
    In actual MIDI files, the max length is four bytes. ValueError raised if
    length of inbytes exceeds four. (set limit=False to override this)
    """
    if limit and len(inbytes) > 4:
        raise ValueError("Sequence too long: {}".format(len(inbytes)))

    value = 0
    last = len(inbytes)-1
    for i, b in enumerate(inbytes):
        # check for validity
        if (b > 0x7F) is not (i < last):
            raise ValueError("Byte sequence not valid")
        value = (value << 7) | (b & 0x7F)
    return value


def pack_variable_length(value, limit=True):
    """
    Encode a positive integer as a variable-length number used in
    Standard MIDI files.
    ValueError rasied if value is over 0x0FFFFFFF (=would require >4 bytes).
    Set limit=False to override this.
    """
    if value < 0:
        raise ValueError("Value is negative: {}".format(value))
    if limit and value > 0x0FFFFFFF:
        raise ValueError("Value too large: {}".format(value))

    dest = bytearray()
    dest.append(value & 0x7F)
    value >>= 7
    while value:
        dest.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(dest))


# Keep It Simple, Stupid.
class lazy_property(object):
    """
    AKA reify, cached_property, etc.
    Saves the cached value on the instance attribute.
    Doesn't care about readonlyness, an instance can override to whatever
    they want it to (it's a non-data descriptor)
    """
    def __init__(self, fget):
        self.fget = fget
        self.name = fget.__name__
        self.__doc__ = fget.__doc__

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        val = self.fget(obj)
        # Pyramid's reify uses setattr, cached_property uses __dict__...
        setattr(obj, self.name, val)
        return val


# EXTREME laziness.
# This is one of those premature optimization things where it's probably not
# worth it, but it was fun to write so it was worth it to ME, dammit.
# now with bonus overkill!
class lazy_readonly_property(object):
    """
    Use as a decorator for methods in a class definition (hashable only).
    the wrapped method is called the first time the property is accessed
    and then the value is stored in a weakref.WeakKeyDictionary with the
    instance object as the key. Future accesses retrieve the stored value.
    """
    def __init__(self, fget, doc=None):
        if doc is None:
            doc = fget.__doc__
        self.__doc__ = doc
        self.fget = fget
        self._values = weakref.WeakKeyDictionary()

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        try:
            val = self._values[obj]
        except KeyError:
            val = self.fget(obj)
            self._values[obj] = val
        return val

    def __set__(self, obj, value):
        raise AttributeError("cannot set attribute")


# This is probably not the best way to do this.
def lazy_readonly_setup_property(in_name, setup_method, doc=None):
    """
    Use inside a class definition, eg:
    class Whatever(object):
        def my_setup_method(self):
            do whatever
            self._a = result

        my_property = lazy_readonly_setup_property('_a', my_setup_method)

    instance = Whatever()
    instance.my_property == result

    If instance.my_property is accessed and instance._a is defined, then
    instance._a is returned immediately; otherwise my_setup_method(instance)
    is called before instance._a is returned. Make sure that my_setup_method
    defines the property!

    in_name: the name of the attribute on instances to store in
    """
    def fget(self, in_name=in_name, setup_method=setup_method):
        try:
            return getattr(self, in_name)
        except AttributeError:
            setup_method(self)
            return getattr(self, in_name)
    return property(fget, doc=doc)


def iter_pairs(itr):
    """
    Iterator over each consecutive pair of items in itr:
    s -> (s0, s1), (s1, s2), (s2, s3), ...
    """
    # pairwise recipe from python documentation
    a, b = itertools.tee(itr)
    next(b, None)
    return zip(a, b)


def cumulative_slices(itr_sizes, start=0):
    """
    Yields slices of lengths from the iterator, starting at start.
    s -> slice(start, start+s0), slice(start+s0, start+s0+s1), ...
    no negative values, please, you may get unexpected results
    """
    # iterator of cumulative size sums
    seq = itertools.chain([start], itr_sizes)
    indices = itertools.accumulate(seq)
    return (slice(*x) for x in iter_pairs(indices))


# EXTREME LAZINESS CONTINUED
class LazySequence(collections.abc.Sequence):
    __slots__ = ('_itemfunc', '_length', '_list')

    def __init__(self, length, itemfunc):
        self._itemfunc = itemfunc
        self._length = length
        self._list = [None]*length

    def __len__(self):
        return self._length

    def _get_item(self, idx):
        item = self._list[idx]
        if item is None:
            item = self._itemfunc(idx)
            self._list[idx] = item
        return item

    def __getitem__(self, key):
        if isinstance(key, slice):
            ixs = range(*key.indices(self._length))
            return [self._get_item(idx) for idx in ixs]
        else:
            idx = key.__index__()
            if idx < 0:
                idx += self._length
                if idx < 0:
                    raise IndexError("index out of range")
            return self._get_item(idx)
