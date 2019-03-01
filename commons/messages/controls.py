"""
controls.py

For working with the controls / sysex / etc midi messages
"""

import mido

from . import voices

from ..util import lazy_property
from .wrappers import Control, Rpn

def xg_parameter_change(*args, n=0):
    if n >> 4 != 0:
        raise ValueError(n)
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
        raise ValueError(value)
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
