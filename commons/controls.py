"""
controls.py

For working with the controls / sysex / etc midi messages
"""

import mido


def reverb(msb, lsb):
    return mido.Message(
        'sysex', data=(0x43, 0x10, 0x4c, 0x02, 0x01, 0x00, msb, lsb))


def chorus(msb, lsb):
    return mido.Message(
        'sysex', data=(0x43, 0x10, 0x4c, 0x02, 0x01, 0x20, msb, lsb))


def master_tuning(mm, ll):
    return mido.Message(
        'sysex', data=(0x43, 0x10, 0x27, 0x30, 0x00, 0x00, mm, ll, 0x00))


def master_tuning_val(value):
    if not (-100 <= value <= 100):
        raise ValueError("Value out of range: {}".format(value))
    mm, ll = divmod(value + 128, 16)
    return master_tuning(mm, ll)


def master_volume(mm):
    return mido.Message(
        'sysex', data=(0x7F, 0x7F, 0x04, 0x01, 0x00, mm))


def gm_system_on():
    return mido.Message(
        'sysex', data=(0x7E, 0x7F, 0x09, 0x01))


def local(boolean):
    if boolean:
        val = 0x7F
    else:
        val = 0x00
    return mido.Message('control_change', control=0x7A, value=val)


def set_rpn(msb=0x7F, lsb=0x7F, channel=0):
    return [
        mido.Message(
            'control_change', control=0x65, value=msb, channel=channel),
        mido.Message(
            'control_change', control=0x64, value=lsb, channel=channel)
    ]


def set_bank_program(msb, lsb, program, channel=0):
    return [
        mido.Message(
            'control_change', control=0x00, value=msb, channel=channel),
        mido.Message(
            'control_change', control=0x20, value=lsb, channel=channel),
        mido.Message(
            'program_change', program=program, channel=channel)
    ]


def multisend(port, messages):
    for message in messages:
        port.send(message)


controls = {
    'bank_msb': 0x00,
    'bank_lsb': 0x32,
    'volume': 0x07,
    'pan': 0x0A,
    'reverb': 0x5B,
    'chorus': 0x5D,
    'pedal': 0x40,
    'release': 0x48,
    'modulation': 0x01,
    'expression': 0x0B,
    'portamento_ctrl': 0x54,
    'harmonic': 0x47,
    'attack': 0x49,
    'brightness': 0x4A,
    'rpn_msb': 0x65,
    'rpn_lsb': 0x64,
    'data_msb': 0x06,
    'data_lsb': 0x26,
    'data_inc': 0x60,
    'data_dec': 0x61,
    'sound_off': 0x78,
    'sound_off_xmono': 0x7E,
    'sound_off_xpoly': 0x7F,
    'notes_off': 0x7B,
    'notes_off_xomnioff': 0x7C,
    'notes_off_xomnion': 0x7D,
    'reset_controls': 0x79,
    'local': 0x7A
}
