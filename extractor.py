import mido
#import itertools
import sys
import collections
import os.path
import struct
import argparse

YAMAHA = 0x43
SONG_SECTION_BYTE = 0x0A
REG_SECTION_BYTE = 0x09

# Basic exceptions
class ExtractorError(Exception):
    pass
class MessageParsingError(ExtractorError):
    pass
class MalformedDataError(ExtractorError):
    pass

DumpMessageTuple = collections.namedtuple(
    'DumpMessageTuple', 'header section a_size b_size run payload end')
def parse_dump_message(msg):
    HEADER_SLICE = slice(None, 5)
    TYPE_INDEX = 5
    A_SIZE_SLICE = slice(6, 8)
    B_SIZE_SLICE = slice(8, 10)
    RUN_SLICE = slice(10, 13)
    PAYLOAD_SLICE = slice(13, -1)
    CHECK_SLICE = slice(6, None)

    END_MARKER = (0x7F, 0x7F, 0x7F)

    if msg.type != 'sysex':
        raise MessageParsingError("Incorrect message type")

    header = msg.data[HEADER_SLICE]
    if header[0] != YAMAHA:
        raise MessageParsingError("Not a Yamaha message")

    section = msg.data[TYPE_INDEX]
    if section not in (SONG_SECTION_BYTE, REG_SECTION_BYTE):
        raise MessageParsingError("Unknown data section")

    a_size = unpack_seven(msg.data[A_SIZE_SLICE])
    b_size = unpack_seven(msg.data[B_SIZE_SLICE])

    zbytes = msg.data[RUN_SLICE]

    if zbytes == END_MARKER:
        run = None
        payload = None
        end = True
    else:
        if sum(msg.data[CHECK_SLICE]) % 0x80 != 0:
            raise MessageParsingError("Checksum invalid")
        run = unpack_seven(zbytes)
        end = False
        rpayload = msg.data[PAYLOAD_SLICE]
        if len(rpayload) != a_size:
            raise MessageParsingError("Content length mismatch")
        payload = reconstitute_all(rpayload)

    return DumpMessageTuple(header, section, a_size, b_size, run, payload, end)

def dump_message_section(messages, section=None, verbose=False):
    run = 0
    dmessages = (parse_dump_message(msg) for msg in messages)
    dm = next(dmessages)
    if section is None:
        section = dm.section
    while not dm.end:
        if dm.section != section:
            raise MessageParsingError("Type mismatch")
        if dm.run != run:
            raise MessageParsingError("Running count mismatch")
        run += dm.a_size
        yield dm
        dm = next(dmessages)

def decode_section_messages(messages, section=None):
    return b''.join(dm.payload for dm in dump_message_section(messages, section))


# Utility for reading syx files.
# Probably should be somewhere else
def read_syx_file(infile):
    # like mido.read_syx_file, but takes a binary mode file object instead.
    data = infile.read()

    if data[0] != 0xf0:
        # this makes a new copy of the entire data
        # just to throw it away again... but i don't particularly care
        data = bytearray.fromhex(
            data.translate(None, b'\t\n\r\f\v').decode('latin1'))
    return mido.parse_all(data)

def write_syx_file(outfile, messages):
    for message in messages:
        if message.type == 'sysex':
            outfile.write(message.bin())

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

def slicebyn(obj, n, end=None):
    """Iterator over n-length slices of obj from the range 0 to end.
    end defaults to len(obj)."""
    if end is None:
        end = len(obj)
    return (obj[i:i+n] for i in range(0, end, n))

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
    """The index-th-lowest bit of the byte, as a boolean."""
    return bool((byte >> index) & 0x01)

def boolean_bitarray_tuple(byte, length=8):
    """Unpack a byte into an 8-tuple of boolean values, LSB first."""
    return tuple(boolean_bitarray_get(byte, i) for i in range(length))





class SongData(object):

    BLOCK_COUNT = 0x82
    BLOCK_SIZE = 0x200

    def __init__(self, data):

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

        PRESETSTYLE = b'PresetStyle\0'*5
        MARKER = b'PK0001'

        self._data = memoryview(data)

        # message format checks
        if len(data) != EXPECTED_SIZE:
            raise MalformedDataError("Data wrong length!")
        presetstyle = self._data[PRESETSTYLE_SLICE]
        startmarker = self._data[START_MARKER_SLICE]
        endmarker = self._data[END_MARKER_SLICE]
        if not ((startmarker == endmarker == MARKER) and
                (presetstyle == PRESETSTYLE)):
            raise MalformedDataError("Invalid format")

        # song data
        self.songsfield = boolean_bitarray_tuple(self._data[SONGS_OFFSET])

        trackslice = self._data[TRACKS_SLICE]
        self.tracksfield = tuple(boolean_bitarray_tuple(x) for x in trackslice)

        songdslice = self._data[SONG_DURATION_SLICE]
        self.song_durations = struct.unpack('>5I', songdslice)

        trackdslice = self._data[TRACK_DURATION_SLICE]
        track_durations_all = struct.unpack('>30I', trackdslice)
        self.track_durations = tuple(slicebyn(track_durations_all, 6))

        self._beginningblocks = self._data[BEGINNING_BLOCKS_SLICE]
        self._nextblocks = self._data[NEXT_BLOCKS_SLICE]
        self._blockdata = self._data[BLOCK_DATA_SLICE]

        self._bblocks = tuple(slicebyn(self._beginningblocks, 6))


        self._mystery = self._data[MYSTERY_SLICE]

        self._songsmidi = [None] * 5


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
        # verify and read the length
        tag, length = struct.unpack_from('>4sI', block, 0)
        if tag != b'MTrk':
            raise MalformedDataError("Chunk start not found")
        datalen = length + 8
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
        return struct.pack('>4sI3H', b'MThd', 6, 1, track_count, 96)

    def midi_song_block_iter(self, song):
        # figure out which blocks
        songblocks = [x for x in self._bblocks[song] if x != 0xFF]
        yield self.midi_header(len(songblocks))
        # we want the time track first
        for i in range(-1, len(songblocks)-1):
            yield from self.track_from_block_iter(songblocks[i])

    def get_midi_song(self, song):
        if not self.songsfield[song]:
            raise ValueError("Song not recorded")
        if not self._songsmidi[song]:
            self._songsmidi[song] = b''.join(self.midi_song_block_iter(song))
        return self._songsmidi[song]

    def available_song_indices(self):
        return [i for i, has_song in enumerate(self.songsfield) if has_song]

    def all_available_songs(self):
        for i in range(5):
            try:
                midi = self.get_midi_song(i)
            except ValueError:
                pass
            else:
                yield i, midi

class RegData(object):

    SETTING_SIZE = 0x2C

    REVERB_MAP = {
         1: "01 Hall1",
         2: "02 Hall2",
         3: "03 Hall3",
         4: "04 Room1",
         5: "05 Room2",
         6: "06 Stage1",
         7: "07 Stage2",
         8: "08 Plate1",
         9: "09 Plate2",
        10: "10 Off",
        11: "-- Room",
        12: "-- Stage",
        13: "-- Plate"
    }

    CHORUS_MAP = {
         1: "01 Chorus1",
         2: "02 Chorus2",
         3: "03 Flanger1",
         4: "04 Flanger2",
         5: "05 Off",
         6: "-- Thru",
         7: "-- Chorus",
         8: "-- Celeste",
         9: "-- Flanger"
    }

    HARMONY_MAP = {
         1: "01 Duet",
         2: "02 Trio",
         3: "03 Block",
         4: "04 Country",
         5: "05 Octave",
         6: "06 Trill 1/4 note",
         7: "07 Trill 1/6 note",
         8: "08 Trill 1/8 note",
         9: "09 Trill 1/12 note",
        10: "10 Trill 1/16 note",
        11: "11 Trill 1/24 note",
        12: "12 Trill 1/32 note",
        13: "13 Tremolo 1/4 note",
        14: "14 Tremolo 1/6 note",
        15: "15 Tremolo 1/8 note",
        16: "16 Tremolo 1/12 note",
        17: "17 Tremolo 1/16 note",
        18: "18 Tremolo 1/24 note",
        19: "19 Tremolo 1/32 note",
        20: "20 Echo 1/4 note",
        21: "21 Echo 1/6 note",
        22: "22 Echo 1/8 note",
        23: "23 Echo 1/12 note",
        24: "24 Echo 1/16 note",
        25: "25 Echo 1/24 note",
        26: "26 Echo 1/32 note"
    }

    BOOL_MAP = {
        0x00: "OFF",
        0x7F: "ON"
    }

    SUSTAIN_MAP = {
        0x40: "OFF",
        0x6E: "ON"
    }

    AB_MAP = {
        0xFF: None,
        0x00: "Main A",
        0x05: "Main B"
    }

    ACMP_MAP = {
        0xFF: None,
        0x00: "OFF",
        0x01: "ON"
    }


    REG_SETTING_NAMES =  [
        # front panel
        "Style number",
        "Accompaniment",
        "Main A/B",
        "Tempo",

        "Main Voice number",
        "Dual Voice number",
        "Split Voice number",

        "Harmony",
        "Dual",
        "Split",

        # function menu
        "Style Volume",
        "Transpose",
        "Pitch Bend Range",
        "Split Point",

        "M. Volume",
        "M. Octave",
        "M. Pan",
        "M. Reverb Level",
        "M. Chorus Level",

        "D. Volume",
        "D. Octave",
        "D. Pan",
        "D. Reverb Level",
        "D. Chorus Level",

        "S. Volume",
        "S. Octave",
        "S. Pan",
        "S. Reverb Level",
        "S. Chorus Level",

        "Reverb Type",
        "Chorus Type",
        "Sustain",

        "Harmony Type",
        "Harmony Volume"
    ]

    SFORMAT = '> B BBbbBB Hbbbbb bHbbbbb bHbbbbb bBB bBb B BB 2s B 2s'


    def __init__(self, data):
        START_SLICE = slice(0x000, 0x004)
        SETTINGS_SLICE = slice(0x004, 0x2C4)
        END_SLICE = slice(0x2C4, 0x2C8)
        PAD_SLICE = slice(0x2C8, None)

        EXPECTED_SIZE = 0x2CA

        BOOKEND = b'PSR\x03'
        PADBYTES = b'\x00\x00'

        self._data = memoryview(data)
        # message format checks
        if len(data) != EXPECTED_SIZE:
            raise MalformedDataError("Data wrong length!")
        if not ((self._data[START_SLICE] == self._data[END_SLICE] == BOOKEND)
                and (self._data[PAD_SLICE] == PADBYTES)):
            raise MalformedDataError("Invalid format")

        setting_section = self._data[SETTINGS_SLICE]
        button_sections = slicebyn(setting_section, self.SETTING_SIZE*8)
        self.setting_data = [tuple(slicebyn(x, self.SETTING_SIZE)) for
                              x in button_sections]

    def get_settings(self, button, bank):
        return self.parse_setting_data(self.setting_data[button-1][bank-1])

    @classmethod
    def parse_setting_data(cls, data):
        parsed_values = collections.OrderedDict(
            (x, None) for x in cls.REG_SETTING_NAMES)
        error_list = []

        def note_unusual(message):
            error_list.append(message)
            print(message, file=sys.stderr)

        def range_check_assign(prop, val, lo=0, hi=127):
            if not (lo <= val <= hi):
                note_unusual("{} out of range: {}".format(prop, val))
            parsed_values[prop] = val

        def mapping_check_assign(prop, val, mapping):
            try:
                parsed_values[prop] = mapping[val]
            except KeyError:
                note_unusual("{} unusual value: {}".format(val))
                parsed_values[prop] = val

        # Check for unexpected things
        (firstbyte,
         style_num, style_acmp, spoint1, spoint2, style_ab, style_vol,
         main_num, main_oct, main_vol, main_pan, main_rvb, main_chs,
         split_on,
         split_num, split_oct, split_vol, split_pan, split_rvb, split_chs,
         dual_on,
         dual_num, dual_oct, dual_vol, dual_pan, dual_rvb, dual_chs,
         pbend, rvb_type, chs_type,
         hmny_on, hmny_type, hmny_vol,
         ffbyte,
         tspose, tempo,
         pad1,
         psust,
         pad2) = struct.unpack(cls.SFORMAT, data)

        if firstbyte != 0x01:
            note_unusual('firstbyte is {:02X}'.format(firstbyte))
        if ffbyte != 0xFF:
            note_unusual('ffbyte is {:02X}'.format(ffbyte))
        if not (pad1 == pad2 == b'\x00\x00'):
            note_unusual('padding is {!r} {!r}'.format(pad1, pad2))

        # Style front panel buttons
        if style_num == 0xFF:
            parsed_values['Style number'] = None
        else:
            range_check_assign('Style number', style_num+1, 1, 136)

        mapping_check_assign('Accompaniment', style_acmp, cls.ACMP_MAP)
        mapping_check_assign('Main A/B', style_ab, cls.AB_MAP)

        if tempo == 0xFF:
            parsed_values['Tempo'] = None
        else:
            range_check_assign('Tempo', tempo+32, 32, 280)

        # Voice numbers
        range_check_assign('Main Voice number', main_num+1, 1, 494)
        range_check_assign('Split Voice number', split_num+1, 1, 494)
        range_check_assign('Dual Voice number', dual_num+1, 1, 494)

        # Voice front panel buttons
        mapping_check_assign('Harmony', hmny_on, cls.BOOL_MAP)
        mapping_check_assign('Dual', dual_on, cls.BOOL_MAP)
        mapping_check_assign('Split', split_on, cls.BOOL_MAP)

        # Function Menu
        if style_vol == 0xFF:
            parsed_values['Style Volume'] = None
        else:
            range_check_assign('Style Volume', style_vol)

        range_check_assign('Transpose', tspose-12, -12, +12)
        range_check_assign('Pitch Bend Range', pbend, 1, 12)

        if spoint1 != spoint2:
            note_unusual(
                "Split points don't match: 0x{:02X}, 0x{:02X}".format(
                    spoint1, spoint2))
        range_check_assign('Split Point', spoint1)

        # Main Voice
        range_check_assign('M. Volume', main_vol)
        range_check_assign('M. Octave', main_oct, -2, +2)
        range_check_assign('M. Pan', main_pan)
        range_check_assign('M. Reverb Level', main_rvb)
        range_check_assign('M. Chorus Level', main_chs)

        # Dual Voice
        range_check_assign('D. Volume', dual_vol)
        range_check_assign('D. Octave', dual_oct, -2, +2)
        range_check_assign('D. Pan', dual_pan)
        range_check_assign('D. Reverb Level', dual_rvb)
        range_check_assign('D. Chorus Level', dual_chs)

        # Split Voice
        range_check_assign('S. Volume', split_vol)
        range_check_assign('S. Octave', split_oct, -2, +2)
        range_check_assign('S. Pan', split_pan)
        range_check_assign('S. Reverb Level', split_rvb)
        range_check_assign('S. Chorus Level', split_chs)

        # Effects
        mapping_check_assign('Reverb Type', rvb_type, cls.REVERB_MAP)
        mapping_check_assign('Chorus Type', chs_type, cls.CHORUS_MAP)
        mapping_check_assign('Sustain', psust, cls.SUSTAIN_MAP)

        # Harmony
        mapping_check_assign('Harmony Type', hmny_type, cls.HARMONY_MAP)
        range_check_assign('Harmony Volume', hmny_vol)

        return parsed_values, error_list


def filter_yamaha_sysex(messages):
    for msg in messages:
        if msg.type == 'sysex':
            if msg.data[0] == YAMAHA:
                yield msg

def aside_collector(seq, itr):
    for item in itr:
        seq.append(item)
        yield item

def read_dgx_dump(messages):
    # the poor man's async
    # TODO: actually test how long it takes
    basket = []
    stream = aside_collector(basket, filter_yamaha_sysex(messages))

    song_data = decode_section_messages(stream, SONG_SECTION_BYTE)
    reg_data = decode_section_messages(stream, REG_SECTION_BYTE)

    return song_data, reg_data, basket




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
        dump_song_data, dump_reg_data, basket = read_dgx_dump(messages)
    else:
        with mido.open_input(args.port) as inport:
            dump_song_data, dump_reg_data, basket = read_dgx_dump(inport)

    song_data = SongData(dump_song_data)
    for i, midi in song_data.all_available_songs():
        filename = "{}_UserSong{}.mid".format(args.outprefix, i+1)
        with open(filename, 'xb') as outfile:
            outfile.write(midi)
