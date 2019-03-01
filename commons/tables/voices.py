"""
voices.py
"""

# maybe this sort of thing is better done using some sort of database.

import collections

from . import table_util
from .. import util

class Voice(collections.namedtuple("Voice",
        "number name fullname category msb lsb prog")):
    __slots__ = ()

    def voice_string(self):
        if self.number is None:
            n = "???"
        else:
            n = format(self.number, "03d")
        return f"{n} {self.name} ({self.category})"

    def voice_string_extended(self):
        return f"[{self.msb},{self.lsb},{self.prog}] {self.voice_string()}"

    def __str__(self):
        return self.voice_string_extended()

# The Silent None Voice.
# must redo this properly.....
SILENT = Voice(None, None, None, None, None, None, None)

# Useless Class Strikes Again

class _VoiceLookup(object):

    DictTuple = collections.namedtuple("DictTuple",
        "numbers bank_programs names_nonxg names_xg")

    @util.lazy_property
    def dicts(self):
        _numbers = util.ListMapping(start=1)
        _bank_programs = {}
        _names_nonxg = {}
        _names_xg = {}
        # read in data from csv file
        full_name_count = 0
        for r_voice in table_util.read_csv_table_namedtuple(
            'tables/voices.csv', Voice, (int, str, str, str, int, int, int)
        ):
            # The fullnames are not included if different from name,
            # so we manually handle that
            if r_voice.fullname:
                voice = r_voice
                full_name_count += 1
            else:
                voice = r_voice._replace(fullname=r_voice.name)

            # assign to dictionaries
            _numbers[voice.number] = voice
            _bank_programs[(voice.msb, voice.lsb, voice.prog)] = voice
            if voice.category.startswith("XG"):
                _names_xg[voice.name] = voice
                if voice is r_voice:
                    _names_xg[voice.fullname] = voice
            else:
                _names_nonxg[voice.name] = voice
                if voice is r_voice:
                    _names_nonxg[voice.fullname] = voice

        # check we have everything
        assert (len(_numbers)
                == len(_bank_programs)
                == len(_names_nonxg) + len(_names_xg) - full_name_count)

        return self.DictTuple(_numbers, _bank_programs, _names_nonxg, _names_xg)

    @util.lazy_property
    def names_nonxg_first(self):
        return collections.ChainMap(self.dicts.names_nonxg, self.dicts.names_xg)

    @util.lazy_property
    def names_xg_first(self):
        return collections.ChainMap(self.dicts.names_xg, self.dicts.names_nonxg)

    @util.lazy_property
    def numbers(self):
        return self.dicts.numbers

    @util.lazy_property
    def bank_programs(self):
        return self.dicts.bank_programs

_LOOKUP = _VoiceLookup()

def from_name(name, prefer_xg=False):
    """
    Look up a voice by name.
    By default in the case of duplicate names the non-XG voice is preferred
    (use the prefer_xg argument for the opposite behaviour)
    Returns a Voice namedtuple.
    KeyError raised if no voice has that name.
    """
    if prefer_xg:
        return _LOOKUP.names_xg_first[name]
    return _LOOKUP.names_nonxg_first[name]


def from_number(number):
    """
    Look up a voice by number.
    Returns a Voice namedtuple.
    KeyError raised if no voice has that number.
    """
    return _LOOKUP.numbers[number]


def from_bank_program(msb, lsb, prog):
    """
    Look up a voice by bank and program bytes.
    MSB, LSB and Program bytes must be specified.
    Note that this uses the program byte (0-127), which is one less than
    the program number (1-128).
    Returns a Voice namedtuple.
    KeyError raised if no voice has those bytes.
    """
    return _LOOKUP.bank_programs[(msb, lsb, prog)]


def from_bank_program_default(msb, lsb, prog):
    """
    Look up a voice by bank and program bytes, using from_bank_program
    if no voice has the bytes, then it will try to fall back to the voice.
    Returns None to indicate no change to the voice,
    returns SILENT to indicate that the voice is deactivated,
    returns a regular voice.
    """
    # The behaviour of a program change depends on the bank MSB.
    if msb == 0x7F:  # Drum Kit. Ignore LSB.
        try:
            return from_bank_program(msb, 0, prog)
        except KeyError:
            # If no match, then don't change at all.
            # we'll return None to indicate this.
            return None
    elif msb == 0x7E: # SFX Kit. Exact Match?
        try:
            return from_bank_program(msb, lsb, prog)
        except KeyError:
            # We do have a voice, but it's the null silent voice.
            return SILENT
    else: # Voices
        try:
            # First, try all
            return from_bank_program(msb, lsb, prog)
        except KeyError:
            try:
                # Then, fallback to LSB 0
                return from_bank_program(msb, 0, prog)
            except KeyError:
                # Finally use SILENT.
                return SILENT
