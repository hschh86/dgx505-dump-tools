import mido
import itertools
import sys
import collections
import os.path
import struct
import argparse

YAMAHA = 0x43
SONG_SECTION_BYTE = 0x0A
REG_SECTION_BYTE = 0x09
SECTION_NAMES = {SONG_SECTION_BYTE: "Song data",
                 REG_SECTION_BYTE: "Registration data"}
EXPECTED_LENGTH = {SONG_SECTION_BYTE: 76904, REG_SECTION_BYTE: 816}
EXPECTED_COUNT = {SONG_SECTION_BYTE: 39, REG_SECTION_BYTE: 2}

def errprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# Basic exceptions
class ExtractorError(Exception):
    pass
class MessageParsingError(ExtractorError):
    pass
class MalformedDataError(ExtractorError):
    pass
class NotRecordedError(ExtractorError):
    pass

DumpMessageTuple = collections.namedtuple(
    'DumpMessageTuple', 'message header section a_size b_size run payload end')
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

    return DumpMessageTuple(msg, header, section,
                            a_size, b_size, run, payload, end)

def dump_message_section(messages, section=None, verbose=False):
    run = 0
    dmessages = (parse_dump_message(msg) for msg in messages)
    dm = next(dmessages)
    if section is None:
        section = dm.section
    if verbose:
        count = 0
        section_name = SECTION_NAMES.get(section, "{:02X}".format(section))
        expected_count = EXPECTED_COUNT.get(section, "?")
        expected_run = EXPECTED_LENGTH.get(section, "?")
        count_len = len(str(expected_count))
        run_len = len(str(expected_run))
        errprint("Section: {}".format(section_name))
    while not dm.end:
        if dm.section != section:
            raise MessageParsingError("Type mismatch")
        if dm.run != run:
            raise MessageParsingError("Running count mismatch")
        run += dm.a_size
        if verbose:
            count += 1
            errprint("Message {:>{cl}} of {}, {:>{rl}}/{} data bytes recieved".format(
                count, expected_count, run, expected_run,
                cl=count_len, rl=run_len))
        yield dm
        dm = next(dmessages)
    if verbose:
        count += 1
        errprint("Message {:>{cl}} of {}, end of section".format(
            count, expected_count, cl=count_len, rl=run_len))
    yield dm

def decode_section_messages(messages, section=None, verbose=False):
    # collect messages
    dump_messages = list(dump_message_section(messages, section, verbose))
    full_payload = b''.join(dm.payload for dm in dump_messages if dm.payload)
    return dump_messages, full_payload


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
    SongInfoTuple = collections.namedtuple(
        "SongInfoTuple",
        'name song_active song_duration tracks_active tracks_duration')
    TRACK_NAMES = ('1', '2', '3', '4', '5', 'A')


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

    def midi_song_block_iter(self, n):
        # figure out which blocks
        songblocks = [x for x in self._bblocks[n] if x != 0xFF]
        yield self.midi_header(len(songblocks))
        # we want the time track first
        for i in range(-1, len(songblocks)-1):
            yield from self.track_from_block_iter(songblocks[i])

    def get_midi_song(self, song):
        if not 1 <= song <= 5:
            raise ValueError("Invalid song number: {}".format(song))
        n = song-1
        if not self.songsfield[n]:
            raise NotRecordedError("Song not recorded")
        if not self._songsmidi[n]:
            self._songsmidi[n] = b''.join(self.midi_song_block_iter(n))
        return self._songsmidi[n]

    def all_available_songs(self):
        for i in range(1, 5+1):
            try:
                midi = self.get_midi_song(i)
            except ValueError:
                pass
            else:
                yield i, midi

    def song_info(self, song):
        if not 1 <= song <= 5:
            raise ValueError("Invalid song number: {}".format(song))
        n = song-1
        name = "User Song {}".format(song)
        song_active = self.songsfield[n]
        song_duration = self.song_durations[n]
        tracks_active = self.tracksfield[n]
        tracks_duration = self.track_durations[n]
        return self.SongInfoTuple(name, song_active, song_duration,
                                  tracks_active, tracks_duration)

    def print_song_info(self, song):
        columns = "{:>10} {!s:>10} {:>10}".format
        info = self.song_info(song)
        print(info.name)
        if info.song_active:
            print(columns("", "Recorded", "Duration"))
            print(columns("all", info.song_active, info.song_duration))
            for track, active, duration in zip(
                self.TRACK_NAMES, info.tracks_active, info.tracks_duration):
                print(columns("Track "+track, active, duration))
        else:
            print("Song not recorded.")

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
         6: "06 Trill 1/4",
         7: "07 Trill 1/6",
         8: "08 Trill 1/8",
         9: "09 Trill 1/12",
        10: "10 Trill 1/16",
        11: "11 Trill 1/24",
        12: "12 Trill 1/32",
        13: "13 Tremolo 1/4",
        14: "14 Tremolo 1/6",
        15: "15 Tremolo 1/8",
        16: "16 Tremolo 1/12",
        17: "17 Tremolo 1/16",
        18: "18 Tremolo 1/24",
        19: "19 Tremolo 1/32",
        20: "20 Echo 1/4",
        21: "21 Echo 1/6",
        22: "22 Echo 1/8",
        23: "23 Echo 1/12",
        24: "24 Echo 1/16",
        25: "25 Echo 1/24",
        26: "26 Echo 1/32"
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


    REG_SETTING_FORMATS =  collections.OrderedDict([
        # front panel
        ("Style number", "03d"),
        ("Accompaniment", "s"),
        ("Main A/B", "s"),
        ("Tempo", "3d"),

        ("Main Voice number", "03d"),
        ("Dual Voice number", "03d"),
        ("Split Voice number", "03d"),

        ("Harmony", "s"),
        ("Dual", "s"),
        ("Split", "s"),

        # function menu
        ("Style Volume", "03d"),
        ("Transpose", "02d"),
        ("Pitch Bend Range", "02d"),
        ("Split Point", "03d"),

        ("M. Volume", "03d"),
        ("M. Octave", "1d"),
        ("M. Pan", "03d"),
        ("M. Reverb Level", "03d"),
        ("M. Chorus Level", "03d"),

        ("D. Volume", "03d"),
        ("D. Octave", "1d"),
        ("D. Pan", "03d"),
        ("D. Reverb Level", "03d"),
        ("D. Chorus Level", "03d"),

        ("S. Volume", "03d"),
        ("S. Octave", "1d"),
        ("S. Pan", "03d"),
        ("S. Reverb Level", "03d"),
        ("S. Chorus Level", "03d"),

        ("Reverb Type", "s"),
        ("Chorus Type", "s"),
        ("Sustain", "s"),

        ("Harmony Type", "s"),
        ("Harmony Volume", "03d")
    ])
    REG_SETTING_NAMES = REG_SETTING_FORMATS.keys()



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
        self._setting_data = tuple(slicebyn(setting_section, self.SETTING_SIZE))

    def get_settings(self, bank, button):
        if not 1 <= button <= 2:
            raise ValueError("Invalid button: {}".format(button))
        if not 1 <= bank <= 8:
            raise ValueError("Invalid bank: {}".format(button))
        n = (button-1)*8 + (bank-1)
        return self.parse_setting_data(self._setting_data[n])

    def print_settings(self, bank, button):
        setting_values, unusual_list = self.get_settings(bank, button)
        print("Bank {}, Button {}:".format(bank, button))
        for key, value in setting_values.items():
            try:
                rep = format(value, self.REG_SETTING_FORMATS[key])
            except (TypeError, ValueError):
                rep = str(value)
            print(" {:>18}: {:>3}".format(key,rep))
        if unusual_list:
            print(" {} unusual values:".format(len(unusual_list)))
            for message in unusual_list:
                print(" - {}".format(message))

    @classmethod
    def parse_setting_data(cls, data):
        parsed_values = collections.OrderedDict(
            (x, None) for x in cls.REG_SETTING_NAMES)
        unusual_list = []

        def note_unusual(message):
            unusual_list.append(message)

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

        return parsed_values, unusual_list

def read_syx_file(infile):
    # like mido.read_syx_file, but takes a binary mode file object instead.
    data = infile.read()
    parser = mido.Parser()
    if data[0] == 0xF0:
        parser.feed(data)
    else:
        for line in data.splitlines():
            parser.feed(bytes.fromhex(line.decode('latin1').strip()))
    return list(parser)

def read_syx_file_lazy(infile):
    # lazy version, for when you don't have EOF
    first = infile.read(1)
    parser = mido.Parser()
    if first == b'\xF0':
        parser.feed(first)
        parser.feed(itertools.chain.from_iterable(infile))
    else:
        firstline = first + infile.readline()
        parser.feed(bytes.fromhex(firstline.decode('latin1').strip()))
        parser.feed(itertools.chain.from_iterable(
            bytes.fromhex(line.decode('latin1').strip()) for line in infile))
    yield from parser


def write_syx_file(outfile, messages):
    for message in messages:
        if message.type == 'sysex':
            outfile.write(message.bin())

def filter_yamaha_sysex(messages):
    return (m for m in messages if m.type == 'sysex' and m.data[0] == YAMAHA)

def read_dgx_dump(messages, verbose=False, songonly=False):
    stream = filter_yamaha_sysex(messages)
    dmsgs, song_data = decode_section_messages(
        stream, SONG_SECTION_BYTE, verbose)
    if songonly:
        reg_data = None
    else:
        reg_msgs, reg_data = decode_section_messages(
            stream, REG_SECTION_BYTE, verbose)
        dmsgs.extend(reg_msgs)
    return dmsgs, song_data, reg_data




# argparser stuff
_argparser = argparse.ArgumentParser(description="Extract UserSong MIDI files from a sysex dump")
_argparser.add_argument('input', type=str,
                        help="Port to read from (run 'mido-ports' to list available ports) / Filename")

_ingroup = _argparser.add_argument_group("Input options")
_ingroup.add_argument('-f', '--fileinput', action='store_true',
                      help="Read from file instead of port")
_ingroup.add_argument('-s', '--songonly', action='store_true',
                     help='Ignore the registration memory data')

_outgroup = _argparser.add_argument_group("Output options")
_outgroup.add_argument('-m', '--midiprefix', type=str,
                       help="write out usersong midi with this file prefix")
_outgroup.add_argument('-d', '--dumpfile', type=str,
                       help="write out syx dump with this filename"),
_outgroup.add_argument('-c', '--clobber', action='store_true',
                       help='overwrite files that already exist')

_rgroup = _argparser.add_argument_group("Other options")
_rgroup.add_argument('-v', '--verbose', action='store_true',
                     help='Print progress messages to stderr')
_rgroup.add_argument('-q', '--quiet', action='store_true',
                     help="Don't print the song stats and one-touch-settings to stdout")


if __name__ == "__main__":

    args = _argparser.parse_args()

    if args.fileinput:
        if args.input == '-':
            # stdin in binary mode
            if args.verbose:
                errprint("Reading from stdin")
            messages = read_syx_file_lazy(sys.stdin.buffer)
        else:
            if args.verbose:
                errprint("Reading from file {!r}".format(args.input))
            with open(args.input, 'rb') as infile:
                messages = read_syx_file(infile)
        ddb = read_dgx_dump(messages, args.verbose, args.songonly)
    else:
        if args.verbose:
            errprint("Listening to port {!r}".format(args.input))
        with mido.open_input(args.input) as inport:
            ddb = read_dgx_dump(inport, args.verbose, args.songonly)
        if args.verbose:
            errprint("All messages read from port")

    basket, dump_song_data, dump_reg_data = ddb

    if args.clobber:
        fmode = 'wb'
    else:
        fmode = 'xb'

    if args.dumpfile is not None:
        if args.verbose:
            errprint("Writing dump file {!r}".format(args.dumpfile))
        try:
            with open(args.dumpfile, fmode) as outfile:
                write_syx_file(outfile, (dm.message for dm in basket))
        except FileExistsError:
            errprint("Error: file exists: {!r}. Ignoring...".format(
                args.dumpfile))

    songs = SongData(dump_song_data)
    for i in range(1, 5+1):
        if not args.quiet:
            songs.print_song_info(i)
            print()
        if args.midiprefix is not None:
            try:
                midi = songs.get_midi_song(i)
            except NotRecordedError:
                pass
            else:
                filename = "{}_UserSong{}.mid".format(args.midiprefix, i)
                if args.verbose:
                    errprint("Writing midi file {!r}".format(filename))
                try:
                    with open(filename, fmode) as outfile:
                        outfile.write(midi)
                except FileExistsError:
                    errprint("Error: file exists: {!r}. Ignoring...".format(
                        args.dumpfile))

    if not (args.quiet or args.songonly):
        regs = RegData(dump_reg_data)
        for bank in range(1, 8+1):
            for button in range(1, 2+1):
                regs.print_settings(bank, button)
                print()
