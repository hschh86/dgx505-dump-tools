"""
values.py

Some Enums.
"""

import enum
from collections import namedtuple

from . import util

_slash_surrogator = str.maketrans("_", "/")

class HarmonyType(enum.Enum):
    DUET = 1
    TRIO = 2
    BLOCK = 3
    COUNTRY = 4
    OCTAVE = 5
    TRILL1_4 = 6
    TRILL1_6 = 7
    TRILL1_8 = 8
    TRILL1_12 = 9
    TRILL1_16 = 10
    TRILL1_24 = 11
    TRILL1_32 = 12
    TREMOLO1_4 = 13
    TREMOLO1_6 = 14
    TREMOLO1_8 = 15
    TREMOLO1_12 = 16
    TREMOLO1_16 = 17
    TREMOLO1_24 = 18
    TREMOLO1_32 = 19
    ECHO1_4 = 20
    ECHO1_6 = 21
    ECHO1_8 = 22
    ECHO1_12 = 23
    ECHO1_16 = 24
    ECHO1_24 = 25
    ECHO1_32 = 26

    def __str__(self):
        namestring = str.translate(self.name, _slash_surrogator).title()
        return f"{self.value:02d}({namestring})"

    def d_value(self):
        return self.value


class RCTypeEnum(enum.Enum):

    def d_value(self):
        if self.value > type(self).OFF.value:
            return None
        return self.value

    def _numstring(self):
        off = type(self).OFF.value
        if self.value > off:
            return "---"
        else:
            return f"{self.value:0{len(str(off))}d}"

    def __str__(self):
        return f"{self._numstring()}({str.title(self.name)})"


class ReverbType(RCTypeEnum):
    HALL1 = 1
    HALL2 = 2
    HALL3 = 3
    ROOM1 = 4
    ROOM2 = 5
    STAGE1 = 6
    STAGE2 = 7
    PLATE1 = 8
    PLATE2 = 9
    OFF = 10
    ROOM = 11
    STAGE = 12
    PLATE = 13


class ChorusType(RCTypeEnum):
    CHORUS1 = 1
    CHORUS2 = 2
    FLANGER1 = 3
    FLANGER2 = 4
    OFF = 5
    THRU = 6
    CHORUS = 7
    CELESTE = 8
    FLANGER = 9

# Instead of doing weird tricks to the class instances
# themselves, how about a wrapper class?

class RCTypeCodeLookup(object):
    # It's a perfectly ordinary class.
    def __init__(self, codes):
        self._to_codes = {}
        self._from_codes = {}
        for t, msb, lsb in codes:
            self._to_codes[t] = msb, lsb
            self._from_codes[msb, lsb] = t

    def from_code(self, msb, lsb):
        try:
            val = self._from_codes[msb, lsb]
        except KeyError:
            try:
                val = self._from_codes[msb, 0x00]
            except KeyError:
                val = self._from_codes[0x00, 0x00]
        return val

    def __getitem__(self, key):
        return self._to_codes[key]


ReverbCodes = RCTypeCodeLookup([
    (ReverbType.OFF,     0x00, 0x00),
    (ReverbType.HALL1,   0x01, 0x00),
    (ReverbType.HALL2,   0x01, 0x10),
    (ReverbType.HALL3,   0x01, 0x11),
    (ReverbType.ROOM,    0x02, 0x00),
    (ReverbType.ROOM1,   0x02, 0x11),
    (ReverbType.ROOM2,   0x02, 0x13),
    (ReverbType.STAGE ,  0x03, 0x00),
    (ReverbType.STAGE1,  0x03, 0x10),
    (ReverbType.STAGE2,  0x03, 0x11),
    (ReverbType.PLATE,   0x04, 0x00),
    (ReverbType.PLATE1,  0x04, 0x10),
    (ReverbType.PLATE2,  0x04, 0x11),
])

ChorusCodes = RCTypeCodeLookup([
    (ChorusType.OFF,      0x00, 0x00),
    (ChorusType.THRU,     0x40, 0x00),
    (ChorusType.CHORUS,   0x41, 0x00),
    (ChorusType.CHORUS2,  0x41, 0x02),
    (ChorusType.CELESTE,  0x42, 0x00),
    (ChorusType.CHORUS1,  0x42, 0x11),
    (ChorusType.FLANGER,  0x43, 0x00),
    (ChorusType.FLANGER1, 0x43, 0x08),
    (ChorusType.FLANGER2, 0x43, 0x11),
])


class SwitchBool(enum.Enum):
    ON = True
    OFF = False

    def __str__(self):
        return self.name

    @classmethod
    def from_b(cls, b):
        util.assert_low(b)
        return cls(b >= 0x40)


class Blank(enum.Enum):
    BLANK = None

    def __str__(self):
        return '---'

BLANK = Blank.BLANK

_space_surrogator = str.maketrans("_", " ")

class AcmpSection(enum.Enum):
    MAIN_A = 0x00
    FILL_B = 0x02
    INTRO_A = 0x03
    ENDING_A = 0x04
    MAIN_B = 0x05
    FILL_A = 0x06
    INTRO_B = 0x08
    ENDING_B = 0x09

    def __str__(self):
        return str.translate(self.name, _space_surrogator)


class NoteBase(enum.Enum):
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    A = "A"
    B = "B"


_asciidental_surrogator = str.maketrans("♯♭", "#b")
_rev_surrogator = str.maketrans("#b", "♯♭", "♮")

class NoteAcc(enum.Enum):
    FLAT = "♭"
    SHARP = "♯"
    NAT = ""  # Technically it would be ♮, but we don't sign it

    @classmethod
    def from_name(cls, asc):
        try:
            return cls(asc)
        except ValueError as e:
            if len(asc) != 1:
                raise e
            return cls(asc.translate(_rev_surrogator))

    def ascii(self):
        return str.translate(self.value, _asciidental_surrogator)


class RootNote(namedtuple("RootNote", "base acc")):
    __slots__ = ()

    def __new__(cls, base, acc=NoteAcc.NAT):
        if base not in NoteBase or acc not in NoteAcc:
            raise ValueError(f"Invalid note {base!r} {acc!r}")
        return super().__new__(cls, base, acc)

    def __str__(self):
        return str(self.base.value) + str(self.acc.value)

    def ascii(self):
        """
        The version of the note that uses # and b instead of actual sharp and
        flat signs
        """
        return str(self).translate(_asciidental_surrogator)

    @classmethod
    def from_name(cls, name):
        return RootNote(NoteBase(name[0]), NoteAcc.from_name(name[1:]))


ROOT_NOTE_SEQ = util.ListMapping(enumerate(RootNote.from_name(x) for x in
    ["C", "D♭", "D", "E♭", "E", "F", "F♯", "G", "G♯", "A", "B♭", "B"]))

_ENHARMONIA = {note: i for i, note in ROOT_NOTE_SEQ.items()}
_ENHARMONIA_OFFSET = {NoteAcc.FLAT: -1, NoteAcc.SHARP: +1}

def enharmonia(note):
    try:
        return _ENHARMONIA[note]
    except KeyError:
        b = _ENHARMONIA[RootNote(note.base)]
        a = _ENHARMONIA_OFFSET[note.acc]
        return (b+a) % len(_ENHARMONIA)

def enharmonic(note_a, note_b):
    return enharmonia(note_a) == enharmonia(note_b)


# Classes For Everyone!
class WrappedValue(object):
    """
    A class for wrapping values in.
    """
    __slots__ = ('value')

    def __init__(self, value):
        self.value = value

    # Should we do comparisons? How does that work?
    def __eq__(self, other):
        return self.value == other.value

    def __repr__(self):
        return f"{self.__class__.__name__}({self.value!r})"


class WrappedIntValue(WrappedValue):
    """
    A class for wrapping int values in.
    """
    __slots__ = ()

    def __int__(self):
        return int(self.value)


class FormattedIntValue(WrappedIntValue):
    __slots__ = ('_format_spec')

    def __init__(self, value, format_spec=''):
        super().__init__(value)
        self._format_spec = format_spec

    def __str__(self):
        return format(self.value, self._format_spec)

    def __repr__(self):
        return (f'{self.__class__.__name__}'
                f'({self.value!r}, {self._format_spec!r})')


class NoteValue(WrappedIntValue):
    __slots__ = ()
    @property
    def octave(self):
        return (self.value // 12) - 2

    @property
    def note(self):
        return ROOT_NOTE_SEQ[self.value % 12]

    def __str__(self):
        return f"{self.value:03d}({self.note.ascii()}{self.octave:-d})"


class BytesValue(WrappedValue):
    __slots__ = ()

    def __str__(self):
        return util.hexspace(self.value)

class UnknownBytesValue(BytesValue):
    __slots__ = ()

    def __str__(self):
        return f'<unknown {super().__str__()}>'