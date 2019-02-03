"""
wrappers.py

Wrappers for mido messages.

The intent of these is to have a more friendly way of
displaying and working with control and sysex messages.
"""

import enum
from collections import namedtuple

class _LongformEnum(enum.Enum):
    def __str__(self):
        return _LONGFORM_MAP.get(self, super().__str__())


class MessageType(_LongformEnum):
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    PITCHWHEEL = "pitchwheel"
    PROGRAM_CHANGE = "program_change"
    CONTROL_CHANGE = "control_change"
    SYSEX = "sysex"
    CLOCK = "clock"
    START = "start"
    STOP = "stop"


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


class Rpn(_LongformEnum):
    PITCH_BEND_RANGE = (0x00, 0x00)
    FINE_TUNE = (0x00, 0x01)
    COARSE_TUNE = (0x00, 0x02)
    NULL = (0x7F, 0x7F)


class SysEx(_LongformEnum):
    GM_ON = "GM System ON"
    MASTER_VOL = "MIDI Master Volume"
    MASTER_TUNE = "MIDI Master Tuning"
    REVERB_TYPE = "Reverb Type"
    CHORUS_TYPE = "Chorus Type"
    XG_ON = "XG System ON"
    XG_RESET = "XG All Parameter Reset"


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
    Rpn.PITCH_BEND_RANGE:       "Pitch Bend Range",
    Rpn.FINE_TUNE:              "Channel Fine Tuning",
    Rpn.COARSE_TUNE:            "Channel Coarse Tuning",
    Rpn.NULL:                   "Null",
    SysEx.GM_ON:                "GM System ON",
    SysEx.MASTER_VOL:           "MIDI Master Volume",
    SysEx.MASTER_TUNE:          "MIDI Master Tuning",
    SysEx.REVERB_TYPE:          "Reverb Type",
    SysEx.CHORUS_TYPE:          "Chorus Type",
    SysEx.XG_ON:                "XG System ON",
    SysEx.XG_RESET:             "XG All Parameter Reset",
}


class UnknownControl(namedtuple('UnknownControl', 'value')):
    def __str__(self):
        return "[Control {}]".format(self.value)


class UnknownSysEx(namedtuple('UnknownSysEx', 'value')):
    def __str__(self):
        return "[SysEx {}]".format(" ".join(
            format(b, "02X") for b in self.value
        ))


class UnknownRpn(namedtuple('UnknownRpn', 'value')):
    def __str__(self):
        return "[RPN {:02X} {:02X}".format(*self.value)


class RpnDataCombo(namedtuple('RpnDataCombo', 'control rpn')):
    def __str__(self):
        return "{0.control!s}: {0.rpn!s}".format(self)


class NoteEvent(namedtuple('NoteEvent', 'note')):
    def __str__(self):
        return "Note {!s}".format(self.note)


class WrappedMessage(object):

    def __init__(self,
             message=None, wrap_type=None, value=None):
        """
        Wrap a mido message.
        """
        # I suppose we could use FrozenMessages here,
        # but we are all responsible adults, right?
        self.wrap_type = wrap_type
        self.value = value
        self.message = message

    def __str__(self):
        return " ".join(
            str(i) for i in (self.wrap_type, self.value)
            if i is not None)

    def __repr__(self):
        return "<{!s} {!r}>".format(self, self.message)


class WrappedChannelMessage(WrappedMessage):

    @property
    def channel(self):
        return self.message.channel

    def __str__(self):
        return "{:X} {}".format(self.channel, super().__str__())
