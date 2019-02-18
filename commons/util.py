"""
util.py

Utilities and helper functions that don't require mido

"""
import sys
import itertools
import functools
import collections
import collections.abc

# SysEx Manufacturer ID
YAMAHA = 0x43


# Formatting
onehex = functools.partial(format, format_spec="1X")
twohex = functools.partial(format, format_spec="02X")

def hexspace(seq):
    """
    Returns a string representation as two digit
    hexadecimal numbers separated by spaces for a sequence
    of byte-sized numbers.
    """
    return " ".join(twohex(b) for b in seq)


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
    """Raise ValueError if not seven-bit (i.e. 0 <= byte <= 127) integer"""
    if byte >> 7 != 0:
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


# class lazy_class_property(lazy_property):
#     """
#     A version of lazy_property that acts on the whole class,
#     like a class method.
#     """
#     # This seems dangerous
#     def __get__(self, obj, objtype=None):
#         return super().__get__(objtype)


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
class CachedSequence(collections.abc.Sequence):
    __slots__ = ('_itemfunc', '_length', '_list')

    def __init__(self, length, itemfunc):
        self._itemfunc = itemfunc
        self._length = length
        self._list = [None]*length

    def __len__(self):
        return self._length

    # I think name mangling is meant for this kind of thing
    def __get_item(self, idx):
        item = self._list[idx]
        if item is None:
            item = self._itemfunc(idx)
            self._list[idx] = item
        return item

    def __getitem__(self, key):
        if isinstance(key, slice):
            ixs = range(*key.indices(self._length))
            # returns a list, but who cares really
            return [self.__get_item(idx) for idx in ixs]
        else:
            idx = key.__index__()
            if idx < 0:
                idx += self._length
                if idx < 0:
                    raise IndexError("index out of range")
            return self.__get_item(idx)


# Again, probably not the best way to do this.
class nonclosing_stdstream(object):
    """
    little wrapper around stdin/stdout, for use as context managers.
    doesn't actually close the stream when context manager exits.
    """
    def __init__(self, mode='r'):
        if mode in ('r', 'rt'):
            self.stream = sys.stdin
        elif mode in ('w', 'wt'):
            self.stream = sys.stdout
        elif mode == 'rb':
            self.stream = sys.stdin.buffer
        elif mode == 'wb':
            self.stream = sys.stdout.buffer
        else:
            raise ValueError('invalid mode: {!r}'.format(mode))

    def __enter__(self):
        return self.stream

    def __exit__(self, *args):
        pass


def open_file_stdstream(filename, *args, **kwargs):
    """
    little wrapper around nonclosing_stdstream, for use as context manager
    If filename == '-', returns the nonclosing stdstream context manager,
    else just returns the open file.
    """
    if filename == '-':
        return nonclosing_stdstream(*args, **kwargs)
    else:
        return open(filename, *args, **kwargs)


# A nice Mapping.
class ListMapping(collections.abc.Mapping):
    """
    A mapping like a dict, but it's for a list underneath
    For storing consecutive integer keys.
    """
    def __init__(self, iterable=(), start=0):
        """
        Initialise a ListMapping.
        Items must be added with consecutively increasing integer keys.
        Start is the starting index.
        """
        self._start = start
        self._list = []
        for key, value in iterable:
            self[key] = value
    
    def __getitem__(self, key):
        index = key - self._start
        if index < 0:
            # We don't want to deal with negative indices
            raise KeyError(key)
        try:
            return self._list[key - self._start]
        except IndexError:
            raise KeyError(key)
    
    def __iter__(self):
        return iter(range(self._start, len(self._list)+self._start))
    
    def __len__(self):
        return len(self._list)
    
    # SetItem. We can only set consecutively
    def __setitem__(self, key, value):
        if key == len(self._list)+self._start:
            self._list.append(value)
        else:
            raise IndexError("Key {!r} added in invalid order".format(key))
