"""
maps.py

Mapping classes that map values from one value to a
tuple of (another) value and a corresponding string

These maps implement the Mapping abstract data type.
"""

import collections.abc
import numbers

from .enums import NoteNumber

class BytesAssertMap(collections.abc.Mapping):
    """
    The BytesAssertMap maps one particular 'bytes' sequence to
    itself and its hex string.
    If the key doesn't match, KeyError is raised.
    """
    def __init__(self, expected):
        self.expected = expected
        self.string = expected.hex()

    def __getitem__(self, key):
        if key != self.expected:
            raise KeyError("{} not expected".format(key))
        return self.expected, self.string

    def __iter__(self):
        yield self.expected

    def __len__(self):
        return 1


class RangeMap(collections.abc.Mapping):
    """
    RangeMap maps integers in a range to integers in (possibly another) range,
    with the string as the result integer formatted with a format string.
    """
    def __init__(self, lo=0, hi=127, offset=0, none_val=None,
                 format_string="03d", none_string="---"):
        """
        The output range is set with the lo and hi arguments, which
        are the lower and upper inclusive bounds of the output range.

        The difference between the input and output ranges is the offset argument
        which specifies an offset to be added to the input value to get the output value.

        The output value is formatted with format_string for the string output.

        Optionally, none_val can be specified to map to None, with a resulting
        custom none_string for this value.
        """
        self.lo = lo
        self.hi = hi
        self.offset = offset
        self.none_val = none_val
        self.key_range = range(lo-offset, hi-offset+1)
        self.format = format_string
        self.none_string = none_string

    def __getitem__(self, key):
        # we only want Integral numbers
        if not isinstance(key, numbers.Integral):
            raise KeyError("{} is not integral".format(key))
        if key == self.none_val:
            value = None
            string = self.none_string
        else:
            if key not in self.key_range:
                raise KeyError("{} is out of range".format(key))
            value = key + self.offset
            string = format(value, self.format)
        return value, string

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


class EffectTypeMap(collections.abc.Mapping):
    """
    Map for the effect type enums (Harmony, Chorus, Reverb)
    defined in commons.enums
    """
    def __init__(self, effect_enum_class):
        self.effect_enum_class = effect_enum_class
    
    def __getitem__(self, key):
        try:
            effect = self.effect_enum_class(key)
        except ValueError:
            raise KeyError("No such effect {}".format(key))
        return effect.d_value(), str(effect)
    
    def __iter__(self):
        for effect in self.effect_enum_class:
            yield effect.value

    def __len__(self):
        return len(self.effect_enum_class)


class KeyMap(RangeMap):
    """
    KeyMap is a specialisation of RangeMap. It maps the input numbers
    to the note notation used by the DGX-505. Only the string output is
    different.
    """

    def __init__(self):
        super().__init__(0, 127, 0)

    def __getitem__(self, key):
        number, _ = super().__getitem__(key)
        return number, str(NoteNumber(number))
