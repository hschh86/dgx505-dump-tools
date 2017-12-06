import mido


def reverb(msb, lsb):
    return mido.Message('sysex',
                        data=(0x43, 0x10, 0x4c, 0x02, 0x01, 0x00, msb, lsb))


def chorus(msb, lsb):
    return mido.Message('sysex',
                        data=(0x43, 0x10, 0x4c, 0x02, 0x01, 0x20, msb, lsb))
