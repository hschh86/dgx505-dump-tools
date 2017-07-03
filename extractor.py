import mido
import sys
import collections
import struct
import argparse

YAMAHA = 0x43

def errprint(*args, **kwargs):
    """Print a message to stderr"""
    print(*args, file=sys.stderr, **kwargs)

# Basic exceptions
class ExtractorError(Exception):
    """Base class for custom exceptions"""
    pass


class MessageError(ExtractorError):
    pass


class MessageParsingError(MessageError):
    """Exception raised when something unexpected happens while
    parsing messages"""
    def __init__(self, description, msg=None):
        self.description = description
        self.msg = msg


class MessageSequenceError(MessageError):
    """Exception raised on errors while collecting a sequence of messages"""
    pass


class MalformedDataError(ExtractorError):
    """Exception to be raised when something unexpected happens while
    parsing the data extracted from the messages"""
    pass


class NotRecordedError(ExtractorError):
    """Exception to be raised when
    trying to get something that wasn't recorded"""
    pass


DumpMessageTuple = collections.namedtuple(
    'DumpMessageTuple', 'message header section a_size b_size run payload end')
def parse_dump_message(msg):
    """Parse a bulk dump sysex message into a DumpMessageTuple of properties
    MessageParsingError is raised if the message is not of the correct format
    ValueError can also be raised if something goes wrong...

    DumpMessageTuple attributes:
    message: the original mido.Message object
    header: The first 5 bytes, starting with 0x43 for YAMAHA
    section: Either 0x0A (Song section) or 0x09 (Registration section)
    a_size: full data size (this is the one that gets used)
    b_size: data size (sans padding?)
    run: running total, or None if final message
    payload: the decoded data, or None if final message
    end: Boolean. True if final message, else False.
    """
    HEADER_SLICE = slice(None, 5)
    TYPE_INDEX = 5
    A_SIZE_SLICE = slice(6, 8)
    B_SIZE_SLICE = slice(8, 10)
    RUN_SLICE = slice(10, 13)
    PAYLOAD_SLICE = slice(13, -1)
    CHECK_SLICE = slice(6, None)

    END_MARKER = (0x7F, 0x7F, 0x7F)

    if msg.type != 'sysex':
        raise MessageParsingError("Incorrect message type", msg)

    header = msg.data[HEADER_SLICE]
    if header[0] != YAMAHA:
        raise MessageParsingError("Not a Yamaha message", msg)

    section = msg.data[TYPE_INDEX]

    a_size = unpack_seven(msg.data[A_SIZE_SLICE])
    b_size = unpack_seven(msg.data[B_SIZE_SLICE])

    zbytes = msg.data[RUN_SLICE]

    if zbytes == END_MARKER:
        run = None
        payload = None
        end = True
    else:
        if sum(msg.data[CHECK_SLICE]) % 0x80 != 0:
            raise MessageParsingError("Checksum invalid", msg)
        run = unpack_seven(zbytes)
        end = False
        rpayload = msg.data[PAYLOAD_SLICE]
        if len(rpayload) != a_size:
            raise MessageParsingError("Content length mismatch", msg)
        payload = reconstitute_all(rpayload)

    return DumpMessageTuple(msg, header, section,
                            a_size, b_size, run, payload, end)

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

def boolean_bitarray_get(integer, index):
    """The index-th-lowest bit of the integer, as a boolean."""
    return bool((integer >> index) & 0x01)

def boolean_bitarray_tuple(integer, length=8):
    """Unpack an integer into a tuple of boolean values, LSB first.
    Uses the lowest bits up to length.
    Raises ValueError if any higher bits are set to 1"""
    if integer >= (1 << length):
        raise ValueError("Some bits are too high: {}".format(byte))
    return tuple(boolean_bitarray_get(integer, i) for i in range(length))

def not_none_get(value, not_none):
    """Return value, or not_none if value is None"""
    if value is None:
        return not_none
    else:
        return value

class DataSection(object):
    SECTION_BYTE = None
    SECTION_NAME = None
    EXPECTED_COUNT = None
    EXPECTED_RUN = None


    def __init__(self, message_seq, verbose=False):
        """
        Verifies that all the sizes and running total match and everything.
        MessageParsingError raised if the messages don't match.
        DumpMessageTuples stored in self.dm_list,
        Concatenated payload memoryview in self.data

        message_seq = an iterable of mido messages
        verbose = print status messages to stderr.
        """
        self.dm_list = []

        run = 0
        dmessages = (parse_dump_message(msg) for msg in message_seq)

        try:
            dm = next(dmessages)
        except StopIteration:
            raise MessageSequenceError("Section empty")

        if self.SECTION_BYTE is None:
            self.SECTION_BYTE = dm.section
        if self.SECTION_NAME is None:
            self.SECTION_NAME = "{:02X}".format(self.SECTION_BYTE)

        if verbose:
            count = 0
            expected_count = not_none_get(self.EXPECTED_COUNT, "?")
            expected_run = not_none_get(self.EXPECTED_RUN, "?")
            count_len = len(str(expected_count))
            run_len = len(str(expected_run))
            errprint("Section: {}".format(self.SECTION_NAME))

        while not dm.end:
            if dm.section != self.SECTION_BYTE:
                raise MessageSequenceError("Type mismatch")
            if dm.run != run:
                raise MessageSequenceError("Running count mismatch")
            run += dm.a_size
            if verbose:
                count += 1
                errprint(
                    "Message {:>{cl}} of {}, {:>{rl}}/{} data bytes recieved".format(
                        count, expected_count, run, expected_run,
                        cl=count_len, rl=run_len))
            self.dm_list.append(dm)

            try:
                dm = next(dmessages)
            except StopIteration:
                raise MessageSequenceError("Section incomplete")

        if verbose:
            count += 1
            errprint("Message {:>{cl}} of {}, end of section".format(
                count, expected_count, cl=count_len, rl=run_len))

        self.dm_list.append(dm)
        databytes = b''.join(dm.payload for dm in self.dm_list if dm.payload)

        self.data = memoryview(databytes)

    def iter_messages(self):
        for dm in self.dm_list:
            yield dm.message


class SongData(DataSection):
    """
    Container for all the useful data in a song section of a bulk dump
    """
    SECTION_BYTE = 0x0A
    SECTION_NAME = "Song data"
    EXPECTED_COUNT = 39
    EXPECTED_RUN = 76904

    BLOCK_COUNT = 0x82
    BLOCK_SIZE = 0x200

    def __init__(self, *args, **kwargs):
        """
        data = the concatenated payload data.
        songs are available through the songs attribute.
        """
        super().__init__(*args, **kwargs)

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

        # message format checks
        if len(self.data) != EXPECTED_SIZE:
            raise MalformedDataError("Data wrong length!")
        presetstyle = self.data[PRESETSTYLE_SLICE]
        startmarker = self.data[START_MARKER_SLICE]
        endmarker = self.data[END_MARKER_SLICE]
        if not ((startmarker == endmarker == MARKER) and
                (presetstyle == PRESETSTYLE)):
            raise MalformedDataError("Invalid format")

        # song data
        try:
            songsfield = boolean_bitarray_tuple(self.data[SONGS_OFFSET], 5)
            tracksfield = [boolean_bitarray_tuple(x, 6)
                           for x in self.data[TRACKS_SLICE]]
        except ValueError:
            raise MalformedDataError("Unexpected high bits in the fields")

        songdslice = self.data[SONG_DURATION_SLICE]
        song_durations = struct.unpack('>5I', songdslice)

        trackdslice = self.data[TRACK_DURATION_SLICE]
        track_durations_all = struct.unpack('>30I', trackdslice)

        self._beginningblocks = self.data[BEGINNING_BLOCKS_SLICE]
        self._nextblocks = self.data[NEXT_BLOCKS_SLICE]
        self._blockdata = self.data[BLOCK_DATA_SLICE]

        self._mystery = self.data[MYSTERY_SLICE]

        track_durations = slicebyn(track_durations_all, 6)
        bblocks = slicebyn(self._beginningblocks, 6)
        numbers = range(1, 5+1)

        self.songs = tuple(
            UserSong(self, *params) for params in zip(
                numbers, songsfield, song_durations,
                tracksfield, track_durations, bblocks))

    def get_block_data(self, n):
        """Returns the specified block data, as a memoryview"""
        if 1 <= n <= self.BLOCK_COUNT:
            end = self.BLOCK_SIZE * n
            start = end - self.BLOCK_SIZE
            return self._blockdata[start:end]
        else:
            raise IndexError("Invalid index: {}".format(n))

    def get_next_block_number(self, n):
        """Returns the number of the block following block n"""
        if n < 1:
            raise IndexError("Invalid index: {}".format(n))
        return self._nextblocks[n-1]

    def _block_data_iter(self, start_block, length):
        """Yields data blocks up to length from start_block"""
        num = start_block
        rem = length
        while rem > 0:
            if num == 0xFF:
                raise MalformedDataError("ran out too early")
            elif num == 0x00:
                raise MalformedDataError("referenced empty block")
            block = self.get_block_data(num)
            if rem < self.BLOCK_SIZE:
                block = block[:rem]
            rem -= len(block)
            num = self.get_next_block_number(num)
            yield block

    def get_track_blocks(self, start_block):
        """Gets a track chunk's size and blocks from its starting block number.
        MalformedDataError raised if chunk is invalid somehow
        returns (size, blocks), where:
        size is the total number of bytes in the chunk (including header)
        blocks is a list of the blocks (as memoryviews, with the last one
        truncated appropriately for the chunk size)
        """
        try:
            block = self.get_block_data(start_block)
        except IndexError:
            raise MalformedDataError("Invalid starting block")
        tag, dlength = struct.unpack_from('>4sL', block, 0)
        if tag != b'MTrk':
            raise MalformedDataError("Chunk start not found")
        size = dlength + 8
        blocks = list(self._block_data_iter(start_block, size))
        return size, blocks

    # cereal!
    def _cereal(self):
        return [song._cereal() for song in self.songs]


class UserSong(object):
    """
    Represents one UserSong and associated data and metadata
    """

    UserSongTrack = collections.namedtuple(
        "UserSongTrack", "track name active duration size blocks")

    def __init__(self, songdata, number, active, duration,
                 tracks_active, tracks_duration, start_blocks):
        self.number = number
        self.active = active
        self.duration = duration

        self.name = "User Song {}".format(number)

        self._tracks = []
        # transpose the last track to first so that
        # index 0 = time/chord track A, index 1 = track 1 etc
        TRACK_NAMES = ('Track 1', 'Track 2', 'Track 3',
                       'Track 4', 'Track 5', 'Track A')
        for i in range(-1, 5):
            start_block = start_blocks[i]
            if start_block == 0xFF:
                size = 0
                blocks = None
            else:
                size, blocks = songdata.get_track_blocks(start_block)
            track = self.UserSongTrack(i+1, TRACK_NAMES[i],
                                       tracks_active[i], tracks_duration[i],
                                       size, blocks)
            self._tracks.append(track)

        self._datatracks = [track for track in self._tracks
                            if track.blocks is not None]
        if self._datatracks:
            self.size = 14 + sum(track.size for track in self._datatracks)
        else:
            self.size = 0

        self._smf = None

    def print_info(self):
        """Prints the recorded (active) status, duration (in measures),
        and size (in bytes) for the song overall and each track within, in a
        table.
        Note that Track A can still have data even if not recorded,
        as the track is also used as the time track for the whole song.
        """
        columns = "{:>12} {!s:>10} {:>10} {:>10}".format
        print(columns("", "Recorded", "Duration", "Size"))
        for item in (self, *self._tracks):
            print(columns(item.name, item.active, item.duration, item.size))

    def _midi_blocks_iter(self):
        if not self._datatracks:
            raise NotRecordedError("Song not recorded")
        header = struct.pack('>4sL3H',
                             b'MThd', 6, 1, len(self._datatracks), 96)
        yield header
        for track in self._datatracks:
            yield from track.blocks

    @property
    def midi(self):
        """The MIDI file, as bytes."""
        if self._smf is None:
            self._smf = b''.join(self._midi_blocks_iter())
        return self._smf

    def _cereal(self):
        return collections.OrderedDict([
            ('number', self.number),
            ('name', self.name),
            ('active', self.active),
            ('duration', self.duration),
            ('size', self.size),
            ('tracks', [collections.OrderedDict([
                ('track', track.track),
                ('name', track.name),
                ('active', track.active),
                ('duration', track.duration),
                ('size', track.size)
            ]) for track in self._tracks])
        ])


class RegData(DataSection):
    """
    Container for the useful data in a reg section
    """
    SECTION_BYTE = 0x09
    SECTION_NAME = "Registration data"
    EXPECTED_COUNT = 2
    EXPECTED_RUN = 816

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        START_SLICE = slice(0x000, 0x004)
        SETTINGS_SLICE = slice(0x004, 0x2C4)
        END_SLICE = slice(0x2C4, 0x2C8)
        PAD_SLICE = slice(0x2C8, None)

        EXPECTED_SIZE = 0x2CA
        SETTING_SIZE = 0x2C

        BOOKEND = b'PSR\x03'
        PADBYTES = b'\x00\x00'

        # message format checks
        if len(self.data) != EXPECTED_SIZE:
            raise MalformedDataError("Data wrong length!")
        if not ((self.data[START_SLICE] == self.data[END_SLICE] == BOOKEND)
                and (self.data[PAD_SLICE] == PADBYTES)):
            raise MalformedDataError("Invalid format")

        # data is stored by button, then bank
        # (i.e. all the settings for a button are together)
        button_list = []
        button_sections = slicebyn(self.data[SETTINGS_SLICE], SETTING_SIZE*8)
        for button_num, button_section in zip(range(1, 2+1), button_sections):
            bank_list = []
            set_sections = slicebyn(button_section, SETTING_SIZE)
            for bank_num, set_section in zip(range(1, 8+1), set_sections):
                reg = RegSetting(bank_num, button_num, set_section)
                bank_list.append(reg)
            button_list.append(bank_list)
        # it's more convenient to store and display as bank, then button
        self.settings = tuple(zip(*button_list))

    def get_settings(self, bank, button):
        """Get the RegSetting object corresponding to the bank and button"""
        if not 1 <= button <= 2:
            raise ValueError("Invalid button: {}".format(button))
        if not 1 <= bank <= 8:
            raise ValueError("Invalid bank: {}".format(button))
        return self.settings[bank-1][button-1]

    def __iter__(self):
        """Iterate through settings, grouped by bank then button"""
        for bank in self.settings:
            yield from bank

    def _cereal(self):
        return [setting._cereal() for setting in self]


class RegSetting(collections.abc.Mapping):

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

    SettingValue = collections.namedtuple("SettingValue", "value raw unusual")

    def __init__(self, bank, button, data):

        self.bank = bank
        self.button = button

        self._dict = collections.OrderedDict(
            (x, None) for x in self.REG_SETTING_NAMES)
        self._unusual = []

        self._parse_data(data)

    def _note_unusual(self, message):
        # Do something with the message, like put it in a list
        self._unusual.append(message)

    def _range_check_assign(self, prop, raw,
                            lo=0, hi=127, offset=0, noneval=None):
        """Assign a value to a property, checking if value falls within range
        If value doesn't, _note_unusual will be called, and the 'unusual'
        field will have a message (instead of None).
        prop = property name
        raw = raw value (stored in raw field of the SettingValue tuple)
        lo = lower bound (inclusive)
        hi = upper bound (inclusive)
        offset = value to add to raw before range check
        noneval = if raw == noneval, value becomes None. (check is skipped)

        self._dict[prop] is assigned a SettingValue(value, raw, unusual) tuple
        """
        unusual = None
        if raw == noneval:
            value = None
        else:
            value = raw + offset
            if not (lo <= value <= hi):
                unusual = "{} out of range: {}".format(prop, value)
                self._note_unusual(unusual)
        self._dict[prop] = self.SettingValue(value, raw, unusual)

    def _mapping_check_assign(self, prop, raw, mapping):
        """Assign a value to a property, where value is mapping[raw]
        If mapping doesn't have key, _note_unusual will be called,
        and the 'unusual' field will have a message (instead of None).

        self._dict[prop] is assigned a SettingValue(value, raw, unusual) tuple
        """
        unusual = None
        try:
            value = mapping[raw]
        except KeyError:
            value = raw
            unusual = "{} unusual value: {}".format(val)
            self._note_unusual(unusual)
        self._dict[prop] = self.SettingValue(value, raw, unusual)

    def _parse_data(self, data):
        """Parse the data into self._dict and self._unusual.
        Does checks, but messages are put into self._unusual instead of
        raised as exceptions.
        """
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
         pad2) = struct.unpack(self.SFORMAT, data)

        if firstbyte != 0x01:
            self._note_unusual('firstbyte is {:02X}'.format(firstbyte))
        if ffbyte != 0xFF:
            self._note_unusual('ffbyte is {:02X}'.format(ffbyte))
        if not (pad1 == pad2 == b'\x00\x00'):
            self._note_unusual('padding is {!r} {!r}'.format(pad1, pad2))

        # Style front panel buttons
        self._range_check_assign('Style number', style_num, 1, 136,
                                 offset=+1, noneval=0xFF)

        self._mapping_check_assign('Accompaniment', style_acmp, self.ACMP_MAP)
        self._mapping_check_assign('Main A/B', style_ab, self.AB_MAP)

        self._range_check_assign('Tempo', tempo, 32, 280,
                                 offset=+32, noneval=0xFF)

        # Voice numbers
        self._range_check_assign('Main Voice number', main_num, 1, 494,
                                 offset=+1)
        self._range_check_assign('Split Voice number', split_num, 1, 494,
                                 offset=+1)
        self._range_check_assign('Dual Voice number', dual_num, 1, 494,
                                 offset=+1)

        # Voice front panel buttons
        self._mapping_check_assign('Harmony', hmny_on, self.BOOL_MAP)
        self._mapping_check_assign('Dual', dual_on, self.BOOL_MAP)
        self._mapping_check_assign('Split', split_on, self.BOOL_MAP)

        # Function Menu
        self._range_check_assign('Style Volume', style_vol, noneval=0xFF)

        self._range_check_assign('Transpose', tspose, -12, +12, offset=-12)
        self._range_check_assign('Pitch Bend Range', pbend, 1, 12)

        if spoint1 != spoint2:
            self._note_unusual(
                "Split points don't match: 0x{:02X}, 0x{:02X}".format(
                    spoint1, spoint2))
        self._range_check_assign('Split Point', spoint1)

        # Main Voice
        self._range_check_assign('M. Volume', main_vol)
        self._range_check_assign('M. Octave', main_oct, -2, +2)
        self._range_check_assign('M. Pan', main_pan)
        self._range_check_assign('M. Reverb Level', main_rvb)
        self._range_check_assign('M. Chorus Level', main_chs)

        # Dual Voice
        self._range_check_assign('D. Volume', dual_vol)
        self._range_check_assign('D. Octave', dual_oct, -2, +2)
        self._range_check_assign('D. Pan', dual_pan)
        self._range_check_assign('D. Reverb Level', dual_rvb)
        self._range_check_assign('D. Chorus Level', dual_chs)

        # Split Voice
        self._range_check_assign('S. Volume', split_vol)
        self._range_check_assign('S. Octave', split_oct, -2, +2)
        self._range_check_assign('S. Pan', split_pan)
        self._range_check_assign('S. Reverb Level', split_rvb)
        self._range_check_assign('S. Chorus Level', split_chs)

        # Effects
        self._mapping_check_assign('Reverb Type', rvb_type, self.REVERB_MAP)
        self._mapping_check_assign('Chorus Type', chs_type, self.CHORUS_MAP)
        self._mapping_check_assign('Sustain', psust, self.SUSTAIN_MAP)

        # Harmony
        self._mapping_check_assign('Harmony Type', hmny_type, self.HARMONY_MAP)
        self._range_check_assign('Harmony Volume', hmny_vol)

    def print_settings(self):
        print("Bank {}, Button {}:".format(self.bank, self.button))
        for key, (value, raw, unusual) in self._dict.items():
            try:
                rep = format(value, self.REG_SETTING_FORMATS[key])
            except (TypeError, ValueError):
                rep = str(value)
            print(" {:>18}: {:>3}".format(key, rep))
        if self._unusual:
            print(" {} unusual values:".format(len(self._unusual)))
            for message in self._unusual:
                print(" - {}".format(message))

    # Methods required for Mapping abc: use underlying self._dict
    def __getitem__(self, key):
        return self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    # cereal
    def _cereal(self):
        return collections.OrderedDict(
            (key, value.value) for key, value in self._dict.items())


class DgxDump(object):
    # Object-Orientation?
    # More Abstractions, More Often!

    def __init__(self, messages, verbose=False, songonly=False):
        self.songonly = songonly

        stream = filter_yamaha_sysex(messages)

        self.song_data = SongData(stream, verbose)
        self._sections = [self.song_data]

        if songonly:
            self.reg_data = None
        else:
            self.reg_data = RegData(stream, verbose)
            self._sections.append(self.reg_data)

    def iter_messages(self):
        for section in self._sections:
            yield from section.iter_messages()

    def write_syx(self, outfile):
        write_syx_file(outfile, self.iter_messages())

    def _cereal(self):
        return collections.OrderedDict([
            ('song_data', self.song_data._cereal()),
            ('reg_data', self.reg_data._cereal() if self.reg_data else None)
        ])


def read_syx_file(infile):
    """Read in a binary or hex syx file.
    Takes a binary mode file object.
    (like mido.read_syx_file, but uses file objects)
    Returns iterator over mido Messages
    """
    data = infile.read()
    parser = mido.Parser()
    if data[0] == 0xF0:
        parser.feed(data)
    else:
        for line in data.splitlines():
            parser.feed(bytes.fromhex(line.decode('latin1').strip()))
    return iter(parser)

def write_syx_file(outfile, messages):
    """Write a binary syx file.
    Takes a binary mode file object
    (like mido.write_syx_file, but uses file objects.)
    """
    for message in messages:
        if message.type == 'sysex':
            outfile.write(message.bin())

def filter_yamaha_sysex(messages):
    return (m for m in messages if m.type == 'sysex' and m.data[0] == YAMAHA)

def _read_dump_from_filename(filename, verbose=False, songonly=False):
    # if filename == '-':
    #     # stdin in binary mode
    #     # Needs EOF.
    #     if args.verbose:
    #         errprint("Reading from stdin")
    #     messages = read_syx_file(sys.stdin.buffer)
    # else:
    if verbose:
        errprint("Reading from file {!r}".format(filename))
    with open(filename, 'rb') as infile:
        messages = read_syx_file(infile)
    if verbose:
        errprint("All messages read from file")
    return DgxDump(messages, verbose, songonly)

def _read_dump_from_portname(portname, verbose=False, songonly=False):
    with mido.open_input(portname) as inport:
        if verbose:
            errprint("Listening to port {!r}".format(inport.name))
        dump = DgxDump(inport, verbose, songonly)
        if verbose:
            errprint("All messages read from port")
    return dump

# argparser stuff
_argparser = argparse.ArgumentParser(
    description="Extract UserSong MIDI files from a sysex dump")
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

def _main(args):
    if args.fileinput:
        dump = _read_dump_from_filename(args.input, args.verbose, args.songonly)
    else:
        dump = _read_dump_from_portname(args.input, args.verbose, args.songonly)

    if args.clobber:
        fmode = 'wb'
    else:
        fmode = 'xb'

    if args.dumpfile is not None:
        if args.verbose:
            errprint("Writing dump file {!r}".format(args.dumpfile))
        try:
            with open(args.dumpfile, fmode) as outfile:
                dump.write_syx(outfile)
        except FileExistsError:
            errprint("Error: file exists: {!r}. Ignoring...".format(
                args.dumpfile))

    for song in dump.song_data.songs:
        if not args.quiet:
            song.print_info()
            print()
        if args.midiprefix is not None:
            try:
                midi = song.midi
            except NotRecordedError:
                pass
            else:
                filename = "{}_UserSong{}.mid".format(
                    args.midiprefix, song.number)
                if args.verbose:
                    errprint("Writing midi file {!r}".format(filename))
                try:
                    with open(filename, fmode) as outfile:
                        outfile.write(midi)
                except FileExistsError:
                    errprint("Error: file exists: {!r}. Ignoring...".format(
                        filename))

    if not (args.quiet or args.songonly):
        for setting in dump.reg_data:
            setting.print_settings()
            print()

if __name__ == "__main__":
    args = _argparser.parse_args()
    _main(args)
