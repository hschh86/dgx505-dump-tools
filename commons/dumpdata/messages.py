import collections

from ..exceptions import MessageParsingError, MessageSequenceError
from ..util import YAMAHA, eprint, unpack_seven, reconstitute_all, not_none_get


DumpMessageTuple = collections.namedtuple(
    'DumpMessageTuple', 'message header section a_size b_size run payload end')


def parse_dump_message(msg):
    """
    Parse a bulk dump sysex message into a DumpMessageTuple of properties
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
            eprint("Section: {}".format(self.SECTION_NAME))

        while not dm.end:
            if dm.section != self.SECTION_BYTE:
                raise MessageSequenceError("Type mismatch")
            if dm.run != run:
                raise MessageSequenceError("Running count mismatch")
            run += dm.a_size
            if verbose:
                count += 1
                eprint(
                    ("Message {:>{cl}} of {}, "
                     "{:>{rl}}/{} data bytes recieved").format(
                        count, expected_count, run, expected_run,
                        cl=count_len, rl=run_len))
            self.dm_list.append(dm)

            try:
                dm = next(dmessages)
            except StopIteration:
                raise MessageSequenceError("Section incomplete")

        if verbose:
            count += 1
            eprint("Message {:>{cl}} of {}, end of section".format(
                count, expected_count, cl=count_len, rl=run_len))

        self.dm_list.append(dm)
        databytes = b''.join(dm.payload for dm in self.dm_list if dm.payload)

        self.data = memoryview(databytes)

    def iter_messages(self):
        for dm in self.dm_list:
            yield dm.message
