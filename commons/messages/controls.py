"""
controls.py

For working with the controls / sysex / etc midi messages
"""

import enum
import mido

from . import voices

from ..util import lazy_property


class MessageType(enum.Enum):
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    PITCHWHEEL = "pitchwheel"
    PROGRAM_CHANGE = "program_change"
    CONTROL_CHANGE = "control_change"
    SYSEX = "sysex"
    CLOCK = "clock"
    START = "start"
    STOP = "stop"


class Control(enum.Enum):
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


class Rpn(enum.Enum):
    PITCH_BEND_RANGE = (0x00, 0x00)
    FINE_TUNE = (0x00, 0x01)
    COARSE_TUNE = (0x00, 0x02)
    NULL = (0x7F, 0x7F)


class SysEx(enum.Enum):
    GM_ON = "GM System ON"
    MASTER_VOL = "MIDI Master Volume"
    MASTER_TUNE = "MIDI Master Tuning"
    REVERB_TYPE = "Reverb Type"
    CHORUS_TYPE = "Chorus Type"
    XG_ON = "XG System ON"
    XG_RESET = "XG All Parameter Reset"


longform = {
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


def xg_parameter_change(*args, n=0):
    if n >> 4 != 0:
        raise ValueError("invalid n: {}".format(n))
    return mido.Message(
        'sysex', data=(0x43, 0x10 | n, 0x4C)+args)


def reverb_type(msb, lsb):
    return xg_parameter_change(0x02, 0x01, 0x00, msb, lsb)


def chorus_type(msb, lsb):
    return xg_parameter_change(0x02, 0x01, 0x20, msb, lsb)


def master_tune(mm, ll):
    return mido.Message(
        'sysex', data=(0x43, 0x10, 0x27, 0x30, 0x00, 0x00, mm, ll, 0x00))


def master_tune_val(value):
    if not (-100 <= value <= 100):
        raise ValueError("Value out of range: {}".format(value))
    mm, ll = divmod(value + 128, 16)
    return master_tune(mm, ll)


def master_vol(mm):
    return mido.Message(
        'sysex', data=(0x7F, 0x7F, 0x04, 0x01, 0x00, mm))


def gm_on():
    return mido.Message(
        'sysex', data=(0x7E, 0x7F, 0x09, 0x01))


def xg_on():
    return xg_parameter_change(0x00, 0x00, 0x7E, 0x00)


def xg_reset():
    return xg_parameter_change(0x00, 0x00, 0x7F, 0x00)


def cc(control, value=0, channel=0):
    if isinstance(control, Control):
        control = control.value
    return mido.Message(
        'control_change', control=control, value=value, channel=channel)


def local(boolean):
    if boolean:
        val = 0x7F
    else:
        val = 0x00
    return cc(Control.LOCAL, value=val)


def set_rpn(rpn=Rpn.NULL, channel=0):
    if isinstance(rpn, Rpn):
        rpn = rpn.value
    msb, lsb = rpn
    return [
        cc(Control.RPN_MSB, value=msb, channel=channel),
        cc(Control.RPN_LSB, value=lsb, channel=channel)
    ]


def set_bank_program(msb, lsb, program, channel=0):
    return [
        cc(Control.BANK_MSB, value=msb, channel=channel),
        cc(Control.BANK_LSB, value=lsb, channel=channel),
        mido.Message('program_change', program=program, channel=channel)
    ]


def set_voice_numbers(voice_number, channel=0):
    voice = voices.from_number(voice_number)
    return set_bank_program(voice.msb, voice.lsb, voice.prog, channel=channel)


def multisend(port, messages):
    for message in messages:
        port.send(message)
