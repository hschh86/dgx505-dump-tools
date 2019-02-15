"""
values.py

Some Enums.
"""

import enum
from collections import namedtuple

from .util import assert_low, ListMapping

_slash_surrogator = str.maketrans("_", "/")

class EffectTypeEnum(enum.Enum):
    def __str__(self):
        top = self.top()
        if self.value > top:
            numstring = "---"
        else:
            numstring = "{0:0{1}d}".format(self.value, len(str(top)))
        namestring = str.translate(self.name, _slash_surrogator).title()
        return "{}({})".format(numstring, namestring)

    @classmethod
    def top(cls):
        return len(cls.__members__)

    def d_value(self):
        if self.value > self.top():
            return None
        return self.value


class HarmonyType(EffectTypeEnum):
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

# This is a really ugly way to do it, but it works.

def _assign_lookup_dicts(cls, table):
    cls.b_dict = {t: b for t, b in table}
    cls.t_dict = {b: t for t, b in table}

class ReverbChorusTypeEnum(EffectTypeEnum):
    @classmethod
    def top(cls):
        return cls.OFF.value

    def to_b(self):
        return self.b_dict[self]

    @classmethod
    def from_b(cls, msb, lsb):
        try:
            val = cls.t_dict[msb, lsb]
        except KeyError:
            try:
                val = cls.t_dict[msb, 0x00]
            except KeyError:
                val = cls.t_dict[0x00, 0x00]
        return val


class ReverbType(ReverbChorusTypeEnum):
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

_assign_lookup_dicts(ReverbType, (
    (ReverbType.OFF,    (0x00, 0x00)),
    (ReverbType.HALL1,  (0x01, 0x00)),
    (ReverbType.HALL2,  (0x01, 0x10)),
    (ReverbType.HALL3,  (0x01, 0x11)),
    (ReverbType.ROOM,   (0x02, 0x00)),
    (ReverbType.ROOM1,  (0x02, 0x11)),
    (ReverbType.ROOM2,  (0x02, 0x13)),
    (ReverbType.STAGE,  (0x03, 0x00)),
    (ReverbType.STAGE1, (0x03, 0x10)),
    (ReverbType.STAGE2, (0x03, 0x11)),
    (ReverbType.PLATE,  (0x04, 0x00)),
    (ReverbType.PLATE1, (0x04, 0x10)),
    (ReverbType.PLATE2, (0x04, 0x11)),
))



class ChorusType(ReverbChorusTypeEnum):
    CHORUS1 = 1
    CHORUS2 = 2
    FLANGER1 = 3
    FLANGER2 = 4
    OFF = 5
    THRU = 6
    CHORUS = 7
    CELESTE = 8
    FLANGER = 9

_assign_lookup_dicts(ChorusType, (
    (ChorusType.OFF, (0x00, 0x00)),
    (ChorusType.THRU, (0x40, 0x00)),
    (ChorusType.CHORUS, (0x41, 0x00)),
    (ChorusType.CHORUS2, (0x41, 0x02)),
    (ChorusType.CELESTE, (0x42, 0x00)),
    (ChorusType.CHORUS1, (0x42, 0x11)),
    (ChorusType.FLANGER, (0x43, 0x00)),
    (ChorusType.FLANGER1, (0x43, 0x08)),
    (ChorusType.FLANGER2, (0x43, 0x11)),
))


class SwitchBool(enum.Enum):
    ON = True
    OFF = False

    def __str__(self):
        return self.name

    @classmethod
    def from_b(cls, b):
        assert_low(b)
        return cls(b >= 0x40)


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
            raise ValueError("Invalid note {!r} {!r}".format(base, acc))
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


ROOT_NOTE_SEQ = ListMapping(enumerate(RootNote.from_name(x) for x in 
    ["C", "D♭", "D", "E♭", "E", "F", "F♯", "G", "G♯", "A", "B♭", "B"]))

ENHARMONIA = {note: i for i, note in ROOT_NOTE_SEQ.items()}
for base in NoteBase:
    i = ENHARMONIA[RootNote(base)]
    l = len(ROOT_NOTE_SEQ)
    for acc, j in [(NoteAcc.FLAT, -1), (NoteAcc.SHARP, +1)]:
        ENHARMONIA[RootNote(base, acc)] = (i+j) % l


# Classes For Everyone!
class WrappedIntValue(object):
    """
    A class for wrapping int values in.
    """
    def __init__(self, int_value):
        self._int_value = int_value

    def __int__(self):
        return self._int_value

    def hex(self):
        """
        Return a hex string (at least 2 digits padded with 0)
        of the int value
        """
        return format(self._int_value, "02X")


class NoteValue(WrappedIntValue):

    @property
    def octave(self):
        return (int(self) // 12) - 2

    @property
    def note(self):
        return ROOT_NOTE_SEQ[int(self) % 12]

    def __repr__(self):
        return "NoteValue({!r})".format(int(self))

    def __str__(self):
        return "{:03d}({!s}{:-d})".format(int(self), self.note.ascii(), self.octave)
