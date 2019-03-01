"""
maps.py

Mapping classes that map values from one value to a
tuple of (another) value and a corresponding string

These maps implement the Mapping abstract data type.
"""

import functools
import collections.abc
import numbers

from . import values

class BytesAssertMap(collections.abc.Mapping):
    """
    The BytesAssertMap maps one particular 'bytes' sequence to
    a wrapped instance of itself.
    If the key doesn't match, KeyError is raised.
    """
    def __init__(self, expected):
        self.expected = values.BytesValue(expected)

    def __getitem__(self, key):
        if key != self.expected.value:
            raise KeyError(f"{key} not expected")
        return self.expected

    def __iter__(self):
        yield self.expected.value

    def __len__(self):
        return 1


class RangeMapBase(collections.abc.Mapping):
    """
    RangeMapBase maps integers in a range to integers in (possibly another) range,
    and wraps the integers in a specified wrapper class.
    """
    def __init__(self, wrapper, lo, hi, offset, none_val=None, none_obj=values.BLANK):
        """
        Wrapper sets the wrapper class that is applied to output integers.

        The output range is set with the lo and hi arguments, which
        are the lower and upper inclusive bounds of the output range.

        The difference between the input and output ranges is the offset argument
        which specifies an offset to be added to the input value to get the output value.

        Optionally, none_val can be specified to map to a special none_obj, that is not wrapped.
        """
        self.wrapper = wrapper
        self.lo = lo
        self.hi = hi
        self.offset = offset
        self.none_val = none_val
        self.key_range = range(lo-offset, hi-offset+1)
        self.none_obj = none_obj

    def __getitem__(self, key):
        # we only want Integral numbers
        if not isinstance(key, numbers.Integral):
            raise KeyError(f"{key} is not integral")
        if key == self.none_val:
            return self.none_obj
        else:
            if key not in self.key_range:
                raise KeyError(f"{key} is out of range")
            return self.wrapper(key + self.offset)

    # because why not
    def __iter__(self):
        """
        Yields all possible keys from the input range, then the none value
        if specified and not already yielded.
        """
        yield from self.key_range
        if self.none_val is not None and self.none_val not in self.key_range:
            yield self.none_val

    def __len__(self):
        length = len(self.key_range)
        if self.none_val is not None and self.none_val not in self.key_range:
            length += 1
        return length



class RangeMap(RangeMapBase):
    """
    RangeMap maps integers in a range to integers in (possibly another) range,
    and wraps the integers in a WrappedIntValue class specified by format_string
    """
    def __init__(self, lo=0, hi=127, offset=0, none_val=None,
                 format_string="03d", none_obj=values.BLANK):
        """
        The output range is set with the lo and hi arguments, which
        are the lower and upper inclusive bounds of the output range.

        The difference between the input and output ranges is the offset argument
        which specifies an offset to be added to the input value to get the output value.

        format_string specifies the formatting of the wrapped integer.

        Optionally, none_val can be specified to map to a special none_obj, that is not wrapped.
        """
        wrapper = functools.partial(values.FormattedIntValue, format_spec=format_string)
        super().__init__(wrapper, lo=lo, hi=hi, offset=offset,
            none_val=none_val, none_obj=none_obj)


class KeyMap(RangeMapBase):
    """
    KeyMap maps the input numbers to the NoteValue wrappers,
    which have the string as the note notation used by the DGX-505.
    """
    def __init__(self):
        wrapper = values.NoteValue
        super().__init__(wrapper, 0, 127, 0)


class EffectTypeMap(collections.abc.Mapping):
    """
    Map for the effect type enums (Harmony, Chorus, Reverb)
    """
    def __init__(self, effect_enum_class):
        self.effect_enum_class = effect_enum_class

    def __getitem__(self, key):
        try:
            return self.effect_enum_class(key)
        except ValueError:
            raise KeyError(f"No such effect {key}")

    def __iter__(self):
        for effect in self.effect_enum_class:
            yield effect.value

    def __len__(self):
        return len(self.effect_enum_class)
