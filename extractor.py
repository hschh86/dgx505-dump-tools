import mido
import os.path
import struct
import argparse



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


def slicebyn(obj, n, end=None):
    if end is None:
        end = len(obj)
    return (obj[i:i+n] for i in range(0, end, n))


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
    return b''.join(reconstitute(x) for x in slicebyn(inbytes, 8))



def boolean_bitarray_get(byte, index):
    return bool((byte >> index) & 0x01)

def boolean_bitarray_tuple(byte, length=8):
    return tuple(boolean_bitarray_get(byte, i) for i in range(length))

# Dump reading
class ExtractorError(Exception):
    pass
class MessageParsingError(ExtractorError):
    pass
class MalformedDataError(ExtractorError):
    pass

class DumpMessage(object):
    YAMAHA = 0x43
    SONG_TYPE = 0x0A
    REG_TYPE = 0x09

    HEADER_SLICE = slice(None, 5)
    TYPE_INDEX = 5
    A_SIZE_SLICE = slice(6, 8)
    B_SIZE_SLICE = slice(8, 10)
    RUN_SLICE = slice(10, 13)
    PAYLOAD_SLICE = slice(13, -1)
    CHECK_SLICE = slice(6, None)

    END_MARKER = (0x7F, 0x7F, 0x7F)

    def __init__(self, msg):
        self._msg = msg
        if msg.type != 'sysex':
            raise MessageParsingError("Incorrect message type")
        data = msg.data
        self.header = data[self.HEADER_SLICE]
        if self.header[0] != self.YAMAHA:
            raise MessageParsingError("Not a Yamaha message")
        self.type = data[self.TYPE_INDEX]
        if self.type not in (self.SONG_TYPE, self.REG_TYPE):
            raise MessageParsingError("Unknown data type")
        self.a_size = unpack_seven(data[self.A_SIZE_SLICE])
        self.b_size = unpack_seven(data[self.B_SIZE_SLICE])

        zbytes = data[self.RUN_SLICE]
        if zbytes == self.END_MARKER:
            self.run = None
            self.payload = None
            self.end = True
        else:
            if sum(data[self.CHECK_SLICE]) % 128 != 0:
                raise MessageParsingError("Checksum invalid")
            self.run = unpack_seven(zbytes)
            self.end = False
            self.payload = data[self.PAYLOAD_SLICE]
            if len(self.payload) != self.a_size:
                raise MessageParsingError("Content length mismatch")






def checked_messages(messages, dt=None):
    run = 0
    for msg in messages:
        dmsg = DumpMessage(msg)
        if dt is None:
            dt = dmsg.type
        if dmsg.type != dt:
            raise MessageParsingError("Type mismatch")
        if dmsg.end:
            break
        else:
            if dmsg.run != run:
                raise MessageParsingError("Running count mismatch")
            run += dmsg.a_size
            yield dmsg

def decode_section_messages(messages, dt=None):
    data = bytearray()
    for dmsg in checked_messages(messages, dt):
        data.extend(reconstitute_all(dmsg.payload))
    return data


class SongData(object):
    SONGS_OFFSET = 0x00
    MYSTERY_SLICE = slice(0x01, 0x15D)
    TRACKS_SLICE = slice(0x15D, 0x167)
    SONG_DURATION_SLICE = slice(0x167, 0x17B)
    TRACK_DURATION_SLICE = slice(0x17B, 0x1F3)
    PRESETSTYLE_SLICE = slice(0x1F3, 0x22F)
    BEGINNING_BLOCKS_SLICE = slice(0x22F, 0x24D)
    NEXT_BLOCKS_SLICE = slice(0x24D, 0x2CF)
    START_MARKER_SLICE = slice(0x2CF, 0x2D5)
    BLOCK_DATA_SLICE = slice(0x2D5, 0x106D5)
    END_MARKER_SLICE = slice(0x106D5, None)

    EXPECTED_SIZE = 0x106DB

    BLOCK_COUNT = 0x82
    BLOCK_SIZE = 0x200




    PRESETSTYLE = b'PresetStyle\0'*5
    MARKER = b'PK0001'


    def __init__(self, data):

        self._data = memoryview(data)

        # message format checks
        if len(data) != self.EXPECTED_SIZE:
            raise MalformedDataError("Data wrong length!")
        presetstyle = self._data[self.PRESETSTYLE_SLICE]
        startmarker = self._data[self.START_MARKER_SLICE]
        endmarker = self._data[self.END_MARKER_SLICE]
        if not ((startmarker == endmarker == self.MARKER) and
                (presetstyle == self.PRESETSTYLE)):
            raise MalformedDataError("Invalid format")

        # song data
        self.songsfield = boolean_bitarray_tuple(self._data[self.SONGS_OFFSET])

        trackslice = self._data[self.TRACKS_SLICE]
        self.tracksfield = tuple(boolean_bitarray_tuple(x) for x in trackslice)

        songdslice = self._data[self.SONG_DURATION_SLICE]
        self.song_durations = struct.unpack('>5I', songdslice)

        trackdslice = self._data[self.TRACK_DURATION_SLICE]
        track_durations_all = struct.unpack('>30I', trackdslice)
        self.track_durations = tuple(slicebyn(track_durations_all, 6))

        self._beginningblocks = self._data[self.BEGINNING_BLOCKS_SLICE]
        self._nextblocks = self._data[self.NEXT_BLOCKS_SLICE]
        self._blockdata = self._data[self.BLOCK_DATA_SLICE]

        self._bblocks = tuple(slicebyn(self._beginningblocks, 6))


        self._mystery = self._data[self.MYSTERY_SLICE]


    def get_block_data(self, n):
        if 1 <= n <= self.BLOCK_COUNT:
            end = self.BLOCK_SIZE * n
            start = end - self.BLOCK_SIZE
            return self._blockdata[start:end]
        else:
            raise IndexError("Invalid index: {}".format(n))

    def get_next_block_number(self, n):
        if n < 1:
            raise IndexError("Invalid index: {}".format(n))
        return self._nextblocks[n-1]

    def track_from_block_iter(self, block_number):
        block = self.get_block_data(block_number)
        # verify block
        if block[:4] != b'MTrk':
            raise MalformedDataError("Chunk start not found")
        # read the length
        datalen = struct.unpack_from('>I', block, 4)[0] + 8
        # yield the blocks
        while datalen > self.BLOCK_SIZE:
            yield block
            datalen -= len(block)
            block_number = self.get_next_block_number(block_number)
            if block_number == 0xFF:
                raise MalformedDataError("ran out too early")
            elif block_number == 0x00:
                raise MalformedDataError("referenced empty block")
            block = self.get_block_data(block_number)
        yield block[:datalen]

    @staticmethod
    def midi_header(track_count):
        return b'MThd'+struct.pack('>I3H', 6, 1, track_count, 96)

    def midi_song_block_iter(self, song):
        # figure out which blocks
        songblocks = [x for x in self._bblocks[song] if x != 0xFF]
        yield self.midi_header(len(songblocks))
        # we want the time track first
        for i in range(-1, len(songblocks)-1):
            yield from self.track_from_block_iter(songblocks[i])

    def get_midi_song(self, song):
        return b''.join(self.midi_song_block_iter(song))

    def available_songs(self):
        return [i for i, has_song in enumerate(self.songsfield) if has_song]





def filter_yamaha_sysex(messages):
    for msg in messages:
        if msg.type == 'sysex':
            if msg.data[0] == DumpMessage.YAMAHA:
                yield msg

def read_dgx_dump(messages):
    stream = filter_yamaha_sysex(messages)
    data = decode_section_messages(stream, DumpMessage.SONG_TYPE)
    return data



# argparser stuff
_argparser = argparse.ArgumentParser(description="Extract UserSong MIDI files from a sysex dump")
_ingroup = _argparser.add_mutually_exclusive_group(required=True)
_ingroup.add_argument('-p', '--port', type=str,
                     help="Read from port (run 'mido-ports' to list available ports)")
_ingroup.add_argument('-i', '--infile', type=str,
                     help="Read from file")
_argparser.add_argument('-o', '--outprefix', type=str, required=True, help="output file prefix")

if __name__ == "__main__":

    args = _argparser.parse_args()

    if args.infile is not None:
        with open(args.infile, 'rb') as infile:
            messages = read_syx_file(infile)
        dump_song_data = read_dgx_dump(messages)
    else:
        with mido.open_input(args.port) as inport:
            dump_song_data = read_dgx_dump(inport)

    song_data = SongData(dump_song_data)
    for i in song_data.available_songs():
        filename = "{}_UserSong{}.mid".format(args.outprefix, i+1)
        with open(filename, 'xb') as outfile:
            outfile.write(song_data.get_midi_song(i))
