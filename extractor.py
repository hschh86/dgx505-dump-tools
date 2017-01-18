import mido
import os.path


# TEMPORARY -- DEPRECATE LATER
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


# Utility for reading syx files.
# Probably should be somewhere else
def read_syx_file(infile):
    # like mido.read_syx_file, but takes a binary mode file object instead.
    with infile:
        data = infile.read()

    if data[0] != 0xf0:
        # this makes a new copy of the entire data just to throw it away again... but i don't particularly care
        data = bytearray.fromhex(data.translate(None, b'\t\n\r\f\v').decode(errors='replace'))
    return mido.parse_all(data)

# Fun Binary Tools
def assert_low(byte):
    """Raise ValueError if byte > 127"""
    if byte > 0x7F:
        raise ValueError("Byte value out of range: {}".format(byte))

def unpack_seven(inbytes):
    """Reconstruct a number from the seven-bit representation used in
    the SysEx message data.
    Takes a bytes-like object, where each byte is seven bits of the number
    (big-endian byte order)
    Each byte must have its high bit zero, or else ValueError is raised.
    """
    value = 0
    for b in inbytes:
        assert_low(b)
        value = (value << 7) | b
    return value

# just for completeness' sake
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

def reconstitute(inbytes):
    """Unpack a sequence of eight bytes into a bytearray of seven bytes
    where the highest bit of each byte is determined by the eighth byte,
    that is, unpack eight bytes of the bulk dump payload data"""
    if len(inbytes) != 8:
        raise ValueError("There must be eight bytes!")
    dest = bytearray(7)
    lastbyte = inbytes[7]
    assert_low(lastbyte)
    for i in range(7):
        byte = inbytes[i]
        assert_low(byte)
        highbit = (lastbyte << (i+1)) & 0x80
        dest[i] = byte | highbit
    return dest

def reconstitute_all(inbytes):
    """Unpack a sequence with a length a multiple of eight using the
    reconstitute function. Returns a bytes object."""
    if len(inbytes) % 8 != 0:
        raise ValueError("There must be a multiple of eight bytes!")
    # would a memoryview object instead of a slice would be better here?
    return b''.join(reconstitute(inbytes[i:i+8]) for i in range(0, len(inbytes), 8))


def read_dgx_dump(messages):
    """Takes a sequence of DGX-505 bulk dump sysex messages,
    and tries to read em'.
    """
    pass



if __name__ == "__main__":
    import argparse
    argparser = argparse.ArgumentParser(description="Extract UserSong MIDI files from a sysex dump")
    ingroup = argparser.add_mutually_exclusive_group(required=True)
    ingroup.add_argument('-p', '--port', type=str,
                         help="Read from port (run 'mido-ports' to list available ports)")
    ingroup.add_argument('-i', '--infile', type=str,
                         help="Read from file")
    argparser.add_argument('-o', '--outfile', type=str, required=True, help="Write to out file thing")
    args = argparser.parse_args()

    with open(args.infile, 'rb') as infile:
        gs = read_syx_file(infile)
    if os.path.exists(args.outfile):
        # not 100% safe in the unlikely event of race conditions but it's good enough
        raise FileExistsError("File exists: {!r}".format(args.outfile))
    else:
        mido.write_syx_file(args.outfile, gs) # if with file object support i should use x but whatever
