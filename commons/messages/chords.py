"""
chords.py

Classes and utilities for handling and representing the chord change information.
"""

import collections
from functools import partial

from . import table_util
from .. import util
from ..values import (RootNote, NoteBase, NoteAcc,
     _asciidental_surrogator, ROOT_NOTE_SEQ)

ChordType = collections.namedtuple('ChordType', 'code name abbr abbr_format disp_format')

class _ChordLookup(object):

    @util.lazy_property
    def codes(self):
        return table_util.read_csv_table_namedtuple_listmapping(
            'tables/chords.csv', ChordType, [partial(int, base=16), str, str, str, str])

    @util.lazy_property
    def names(self):
        return {c.name: c for c in self.codes.values()}

    @util.lazy_property
    def abbrs(self):
        return {c.abbr: c for c in self.codes.values()}

CHORDS = _ChordLookup()

_ROOT_BASES = {
    0x1: NoteBase.C,
    0x2: NoteBase.D,
    0x3: NoteBase.E,
    0x4: NoteBase.F,
    0x5: NoteBase.G,
    0x6: NoteBase.A,
    0x7: NoteBase.B,
}

_ROOT_ACCS = {
    0x20: NoteAcc.FLAT,
    0x30: NoteAcc.NAT,
    0x40: NoteAcc.SHARP,
}

def byte_note(byte):
    h = byte & 0xF0
    if h == 0x00:
        return ROOT_NOTE_SEQ[byte]
    l = byte & 0x0F
    return RootNote(_ROOT_BASES[l], _ROOT_ACCS[h])

BASS_CODE = 0x1E

def byte_chord(chordbytes):
    # Chord specifications
    # cr ct bn bt
    cr, ct, bn, bt = chordbytes
    root = byte_note(cr)
    bass = byte_note(bn)
    ctype = CHORDS.codes[ct]
    btype = CHORDS.codes[bt]
    if (cr, ct) == (bn, bt):
        # Same -> Ordinary
        return Chord(root, ctype)
    elif bt == BASS_CODE:
        # Extra bass specified
        return Chord(root, ctype, bass)
    raise ValueError(chordbytes)



class Chord(collections.namedtuple('Chord', 'root type bass')):
    __slots__ = ()

    # A Chord has three parts.
    def __new__(cls, root, type, bass=None):
        return super().__new__(cls, root, type, bass)

    def __str__(self):
        # main chord
        chordstring = self.type.abbr_format.format(str(self.root))
        if self.bass is None:
            return chordstring
        else:
            return f"{chordstring}/{self.bass!s}"

    def display(self):
        chordstring = self.type.disp_format.format(str(self.root))
        if chordstring == "" or self.bass is None:
            # for the cc case, nothing is displayed, even if bass
            return chordstring
        else:
            return f"{chordstring}/{self.bass!s}"

    def ascii(self):
        return str(self).translate(_asciidental_surrogator)
