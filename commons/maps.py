import collections.abc
import numbers

class BytesAssertMap(collections.abc.Mapping):
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
    def __init__(self, lo=0, hi=127, offset=0, none_val=None,
                 format="03d", none_string="---"):
        self.lo = lo
        self.hi = hi
        self.offset = offset
        self.none_val = none_val
        self.key_range = range(lo-offset, hi-offset+1)
        self.format = format
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
        yield from self.key_range
        if self.none_val is not None and self.none_val not in self.key_range:
            yield self.none_val

    def __len__(self):
        length = len(self.key_range)
        if self.none_val is not None and self.none_val not in self.key_range:
            length += 1
        return length


class KeyMap(RangeMap):
    NOTES = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B")

    def __init__(self):
        super().__init__(0, 127, 0, None, "03d")

    def __getitem__(self, key):
        number, _ = super().__getitem__(key)
        a, b = divmod(number, 12)
        octave = a-2
        note = self.NOTES[b]
        return number, "{}({}{:-d})".format(number, note, octave)
