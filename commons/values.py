"""
values.py

Some Enums.
"""

import enum
from collections import namedtuple

from .util import assert_low, ListMapping #, lazy_class_property

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
        return "{:02d}({})".format(self.value, namestring)
    
    @classmethod
    def from_number(cls, number):
        try:
            return cls(number)
        except ValueError:
            raise KeyError(number)
    
    @property
    def number(self):
        return self.value

    def d_value(self):
        return self.value

# Slightly Less Ugly But Still Pretty Ugly, Honestly

def RCdictify(cls):
    cls._number_dict = {x.number: x for x in cls}
    cls._code_dict = {x.code: x for x in cls}
    cls._top = cls.OFF.number
    cls._n_digits = len(str(cls._top))
    return cls

class RCTypeEnum(enum.Enum):
    def __init__(self, number, code):
        self.number = number
        self.code = code
    
    # @lazy_class_property
    # def num_dict(cls):
    #     return {x.number: x for x in cls}
    
    # @lazy_class_property
    # def code_dict(cls):
    #     return {x.code: x for x in cls}

   
    @classmethod
    def from_code(cls, msb, lsb):
        try:
            val = cls._code_dict[msb, lsb]
        except KeyError:
            try:
                val = cls._code_dict[msb, 0x00]
            except KeyError:
                val = cls._code_dict[0x00, 0x00]
        return val

    @classmethod
    def from_number(cls, number):
        return cls._number_dict[number]

    def d_value(self):
        if self.number > self._top:
            return None
        return self.number
    
    def _numstring(self):
        if self.d_value() is None:
            return "---"
        else:
            return "{0:0{1}d}".format(self.number, self._n_digits)
    
    def __str__(self):
        return "{}({})".format(self._numstring(), str.title(self.name))


@RCdictify
class ReverbType(RCTypeEnum):
    HALL1  = (1,  (0x01, 0x00))
    HALL2  = (2,  (0x01, 0x10))
    HALL3  = (3,  (0x01, 0x11))
    ROOM1  = (4,  (0x02, 0x11))
    ROOM2  = (5,  (0x02, 0x13))
    STAGE1 = (6,  (0x03, 0x10))
    STAGE2 = (7,  (0x03, 0x11))
    PLATE1 = (8,  (0x04, 0x10))
    PLATE2 = (9,  (0x04, 0x11))
    OFF    = (10, (0x00, 0x00))
    ROOM   = (11, (0x02, 0x00))
    STAGE  = (12, (0x03, 0x00))
    PLATE  = (13, (0x04, 0x00))

@RCdictify
class ChorusType(RCTypeEnum):
    CHORUS1  = (1, (0x42, 0x11))
    CHORUS2  = (2, (0x41, 0x02))
    FLANGER1 = (3, (0x43, 0x08))
    FLANGER2 = (4, (0x43, 0x11))
    OFF      = (5, (0x00, 0x00))
    THRU     = (6, (0x40, 0x00))
    CHORUS   = (7, (0x41, 0x00))
    CELESTE  = (8, (0x42, 0x00))
    FLANGER  = (9, (0x43, 0x00))



class SwitchBool(enum.Enum):
    ON = True
    OFF = False

    def __str__(self):
        return self.name

    @classmethod
    def from_b(cls, b):
        assert_low(b)
        return cls(b >= 0x40)


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
