import mido

def read_hex_syx(filename):
    # workaround, to get avoid a bug? in mido 1.1.18
    # (bytearray.fromhex doesn't like newlines...)
    with open(filename, 'r', errors='replace') as infile:
        hex_lines = infile.readlines()

    # maybe... return mido.parse_all(itertools.chain(bytearray.fromhex(line) for line in data.splitlines())) ??
    data = bytearray()
    for line in hex_lines:
        data.extend(bytearray.fromhex(line.strip()))
    return [msg for msg in mido.Parser(data) if msg.type == 'sysex']


def seven_byte_length(value):
    """Returns the minimum number of bytes required to represent the integer
    if we can use seven bits per byte.
    Positive integers only, please!"""
    q, rem = divmod(value.bit_length(), 7)
    if rem or not q: # (the not q is in case value is 0, we can't have 0 bytes)
        q += 1
    return q
def pack_seven(value, length=None):
    """Packs a positive integer value into the seven-bit representation used
    in the sysex message data."""
    if value < 0:
        raise ValueError("Value is negative: {}".format(value))
    minlen = seven_byte_length(value)
    if length is None:
        length = minlen
    else:
        # if 2**(7*length) < value...
        if minlen > length:
            raise ValueError("Length too short to fit value")
    dest = bytearray(length)
    for i in range(minlen):
        dest[i] = (value & 0x7F)
        value >>= 7
    return bytes(reversed(dest))

def unpack_variable_length(inbytes, limit=True):
    """Reconstruct a number from the variable-length representation used
    in Standard MIDI files. This version only accepts just the entire sequence
    (that is, last byte must have high bit 0, all other bytes must have
    high bit 1).
    In actual MIDI files, the max length is four bytes. ValueError raised if
    length of inbytes exceeds four. (set limit=False to override this)
    """
    if limit and len(inbytes) > 4:
        raise ValueError("Sequence too long: {}".format(len(inbytes)))

    value = 0
    last = len(inbytes)-1
    for i, b in enumerate(inbytes):
        # check for validity
        if (b > 0x7F) is not (i < last):
            raise ValueError("Byte sequence not valid")
        value = (value << 7) | (b & 0x7F)
    return value

def pack_variable_length(value, limit=True):
    """Encode a positive integer as a variable-length number used in
    Standard MIDI files.
    ValueError rasied if value is over 0x0FFFFFFF (=would require >4 bytes).
    Set limit=False to override this."""
    if value < 0:
        raise ValueError("Value is negative: {}".format(value))
    if limit and value > 0x0FFFFFFF:
        raise ValueError("Value too large: {}".format(value))

    dest = bytearray()
    dest.append(value & 0x7F)
    value >>= 7
    while value:
        dest.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(dest))
