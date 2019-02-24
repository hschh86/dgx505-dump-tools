"""
wrappers.py

Wrappers for mido messages.

The intent of these is to have a more friendly way of
displaying and working with control and sysex messages.
"""

import enum
from collections import namedtuple, OrderedDict
from ..util import twohex, hexspace

class _LongformEnum(enum.Enum):
    def __str__(self):
        return _LONGFORM_MAP.get(self, super().__str__())


class _StringValueEnum(enum.Enum):
    def __str__(self):
        return str(self.value)


class MessageType(_LongformEnum):
    # Regular Message Types
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    PITCHWHEEL = "pitchwheel"
    PROGRAM_CHANGE = "program_change"
    CONTROL_CHANGE = "control_change"
    SYSEX = "sysex"
    CLOCK = "clock"
    START = "start"
    STOP = "stop"
    # Meta-Message Types
    TEMPO = "set_tempo"
    SEQSPEC = "sequencer_specific"


class Control(_LongformEnum):
    BANK_MSB = 0x00
    BANK_LSB = 0x20
    VOLUME = 0x07
    PAN = 0x0A
    REVERB = 0x5B
    CHORUS = 0x5D
    PEDAL = 0x40
    RELEASE = 0x48
    MODULATION = 0x01
    EXPRESSION = 0x0B
    PORTAMENTO_CTRL = 0x54
    HARMONIC = 0x47
    ATTACK = 0x49
    BRIGHTNESS = 0x4A
    RPN_MSB = 0x65
    RPN_LSB = 0x64
    DATA_MSB = 0x06
    DATA_LSB = 0x26
    DATA_INC = 0x60
    DATA_DEC = 0x61
    SOUND_OFF = 0x78
    SOUND_OFF_XMONO = 0x7E
    SOUND_OFF_XPOLY = 0x7F
    NOTES_OFF = 0x7B
    NOTES_OFF_XOMNIOFF = 0x7C
    NOTES_OFF_XOMNION = 0x7D
    RESET_CONTROLS = 0x79
    LOCAL = 0x7A

    # Control 5E / 94, not supported by DGX-505,
    # but present in User Song data?
    VARIATION = 0x5E


class Rpn(_LongformEnum):
    PITCH_BEND_RANGE = (0x00, 0x00)
    FINE_TUNE = (0x00, 0x01)
    COARSE_TUNE = (0x00, 0x02)
    NULL = (0x7F, 0x7F)


class SysEx(_StringValueEnum):
    # General
    GM_ON = "GM System ON"
    MASTER_VOL = "MIDI Master Volume"
    MASTER_TUNE = "MIDI Master Tuning"
    REVERB_TYPE = "Reverb Type"
    CHORUS_TYPE = "Chorus Type"
    XG_ON = "XG System ON"
    XG_RESET = "XG All Parameter Reset"
    # Song Exclusive
    CHORD = "Sysex Chord Change"


class SeqSpec(_StringValueEnum):
    # Sequencer-Specific Meta-Messages
    STYLE = "Style"
    STYLE_VOL = "Style Volume"
    SECTION = "Section Change"
    CHORD = "Meta Chord Change"
    # XF Meta-Messages
    XF_VERSION = "XF Version ID"
    GUIDE_TRACK = "Guide Track Flag"


class Special(_StringValueEnum):
    # For things that don't really fit anywhere else
    OCTAVE = "Channel Voice Octave"


_LONGFORM_MAP = {
    MessageType.NOTE_ON:        "Note On",
    MessageType.NOTE_OFF:       "Note Off",
    MessageType.PITCHWHEEL:     "Pitch Bend",
    MessageType.PROGRAM_CHANGE: "Program Change",
    MessageType.CONTROL_CHANGE: "Control Change",
    MessageType.SYSEX:          "System Exclusive",
    MessageType.CLOCK:          "Clock",
    MessageType.START:          "Start",
    MessageType.STOP:           "Stop",
    MessageType.TEMPO:          "Tempo Change",
    MessageType.SEQSPEC:        "Sequencer Specific",
    Control.BANK_MSB:           "Bank MSB",
    Control.BANK_LSB:           "Bank LSB",
    Control.VOLUME:             "Voice Volume",
    Control.PAN:                "Voice Pan",
    Control.REVERB:             "Voice Reverb Level",
    Control.CHORUS:             "Voice Chorus Level",
    Control.PEDAL:              "Pedal Sustain",
    Control.RELEASE:            "Release Time",
    Control.MODULATION:         "Modulation Wheel",
    Control.EXPRESSION:         "Expression",
    Control.PORTAMENTO_CTRL:    "Portamento Control",
    Control.HARMONIC:           "Harmonic Content",
    Control.ATTACK:             "Attack Time",
    Control.BRIGHTNESS:         "Brightness",
    Control.RPN_MSB:            "RPN MSB",
    Control.RPN_LSB:            "RPN LSB",
    Control.DATA_MSB:           "Data Entry MSB",
    Control.DATA_LSB:           "Data Entry LSB",
    Control.DATA_INC:           "Data Increment",
    Control.DATA_DEC:           "Data Decrement",
    Control.SOUND_OFF:          "All Sound OFF",
    Control.SOUND_OFF_XMONO:    "All Sound OFF (MONO)",
    Control.SOUND_OFF_XPOLY:    "All Sound OFF (POLY)",
    Control.NOTES_OFF:          "All Notes OFF",
    Control.NOTES_OFF_XOMNIOFF: "All Notes OFF (OMNI OFF)",
    Control.NOTES_OFF_XOMNION:  "All Notes OFF (OMNI ON)",
    Control.RESET_CONTROLS:     "Reset All Controllers",
    Control.LOCAL:              "Local ON/OFF",
    Control.VARIATION:          "[Voice Variation Level]",
    Rpn.PITCH_BEND_RANGE:       "Pitch Bend Range",
    Rpn.FINE_TUNE:              "Channel Fine Tuning",
    Rpn.COARSE_TUNE:            "Channel Coarse Tuning",
    Rpn.NULL:                   "Null",
}


class UnknownControl(namedtuple('UnknownControl', 'value')):
    __slots__ = ()
    def __str__(self):
        return "[Control {:02X}]".format(self.value)


class UnknownSysEx(namedtuple('UnknownSysEx', 'value')):
    __slots__ = ()
    def __str__(self):
        return "[SysEx {}]".format(hexspace(self.value))


class UnknownSeqSpec(namedtuple('UnknownSeqSpec', 'value')):
    __slots__ = ()
    def __str__(self):
        return "[SeqSpec {}]".format(hexspace(self.value))


class UnknownRpn(namedtuple('UnknownRpn', 'value')):
    __slots__ = ()
    def __str__(self):
        return "[RPN {:02X} {:02X}]".format(*self.value)


class RpnDataCombo(namedtuple('RpnDataCombo', 'control rpn')):
    __slots__ = ()
    def __str__(self):
        return "{0.control!s}: {0.rpn!s}".format(self)


class NoteEvent(namedtuple('NoteEvent', 'note')):
    __slots__ = ()
    def __str__(self):
        return "Note {!s}".format(self.note)

class GuideTracks(namedtuple('GuideTracks', 'rh lh')):
    __slots__ = ()
    @staticmethod
    def channel_format(value):
        if value is None:
            return "OFF"
        else:
            return format(value, "1X")

    def __str__(self):
        return "rh: {}, lh: {}".format(
            self.channel_format(self.rh), self.channel_format(self.lh))

class Bonus(OrderedDict):
    def __str__(self):
        if self:
            return "({})".format(
                " ".join("{}={!s}".format(k, v) for k, v in self.items()))
        else:
            return ""

def bonus_strings(*args):
    pairs = [(k, format(v, *r)) for k, v, u, *r in args if v != u]
    if pairs:
        return Bonus(pairs)
    return None

class WrappedMessage(namedtuple('WrappedMessage', 'message wrap_type value bonus')):
    __slots__ = ()

    def __new__(cls,
             message=None, wrap_type=None, value=None, bonus=None):
        """
        Wrap a mido message.
        """
        # I suppose we could use FrozenMessages here,
        # but we are all responsible adults, right?
        return super().__new__(cls, message, wrap_type, value, bonus)

    def __str__(self):
        return " ".join(
            str(i) for i in (self.wrap_type, self.value, self.bonus)
            if i is not None)

    def __repr__(self):
        return "<{!s} {!r}>".format(self, self.message)


class WrappedChannelMessage(WrappedMessage):

    @property
    def channel(self):
        return self.message.channel

    def __str__(self):
        return "{:X} {}".format(self.channel, super().__str__())
