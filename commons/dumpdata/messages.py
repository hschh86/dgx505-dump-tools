from ..exceptions import MessageParsingError, MessageSequenceError
from ..util import (YAMAHA, eprint,
                    unpack_seven, reconstitute_all, not_none_get,
                    lazy_readonly_property)


class DumpMessage(object):
    """
    Parse a bulk dump sysex message into a DumpMessage of properties
    MessageParsingError is raised if the message is not of the correct format
    ValueError can also be raised if something goes wrong...

    DumpMessage attributes / properties:
    message: the original mido.Message object
    header: The first 5 bytes, starting with 0x43 for YAMAHA
    section: Either 0x0A (Song section) or 0x09 (Registration section)
    padded_size: full data size
    unpadded_size: data size sans padding
    padding_size: the difference between the sizes, or None if final message
    run: running total, or None if final message
    raw_payload: the encoded data
    padded_payload: decoded data including padding, or None if final message
    payload: the decoded data excluding padding, or None if final message
    end: Boolean. True if final message, else False.
    """
    def __init__(self, message):
        # slices
        HEADER_SLICE = slice(None, 5)
        TYPE_INDEX = 5
        PADDED_SIZE_SLICE = slice(6, 8)
        UNPADDED_SIZE_SLICE = slice(8, 10)
        RUN_SLICE = slice(10, 13)
        PAYLOAD_SLICE = slice(13, -1)
        CHECK_SLICE = slice(6, None)
        # The final message of a section has this in the RUN_SLICE:
        END_MARKER = (0x7F, 0x7F, 0x7F)

        # save this in case we need it
        self.message = message

        # sanity checks
        if message.type != 'sysex':
            raise MessageParsingError("Incorrect message type", message)

        self.header = message.data[HEADER_SLICE]
        if self.header[0] != YAMAHA:
            raise MessageParsingError("Not a Yamaha message", message)

        self.section = message.data[TYPE_INDEX]
        # Sizes
        self.padded_size = unpack_seven(message.data[PADDED_SIZE_SLICE])
        self.unpadded_size = unpack_seven(message.data[UNPADDED_SIZE_SLICE])
        # Run / End marker
        self.zbytes = message.data[RUN_SLICE]
        if self.zbytes == END_MARKER:
            self.end = True
            self.run = None
            self.raw_payload = None
            self.padding_size = None
        else:
            self.end = False
            # quick-and-dirty checksum
            if sum(message.data[CHECK_SLICE]) % 0x80 != 0:
                raise MessageParsingError("Checksum invalid", message)
            # running total of the number of encoded bytes in section so far
            self.run = unpack_seven(self.zbytes)
            # The undecoded contents of the payload go in self.raw_payload
            self.raw_payload = message.data[PAYLOAD_SLICE]
            # content length checks:
            # - padded size
            if len(self.raw_payload) != self.padded_size:
                raise MessageParsingError("Content length mismatch", message)
            # - size difference should be in range 0..6
            self.padding_size = self.padded_size - self.unpadded_size
            if not (0 <= self.padding_size <= 6):
                raise MessageParsingError("Data size mismatch", message)
            # - silly padding check; not strictly necessary
            if self.padding_size:
                lastbyte = self.raw_payload[-1]
                padbytes = self.raw_payload[-1-self.padding_size:-1]
                if (sum(padbytes) + (lastbyte % 2**self.padding_size)) != 0:
                    raise MessageParsingError("Padding bytes not clear",
                                              message)

    @lazy_readonly_property('_padded_payload')
    def padded_payload(self):
        if self.raw_payload is None:
            return None
        return memoryview(reconstitute_all(self.raw_payload))

    @lazy_readonly_property('_payload')
    def payload(self):
        if self.padding_size:
            # trim off the padding bytes
            return self.padded_payload[:-self.padding_size]
        return self.padded_payload


class DataSection(object):
    SECTION_BYTE = None
    SECTION_NAME = None
    EXPECTED_COUNT = None
    EXPECTED_RUN = None

    def __init__(self, message_seq, verbose=False):
        """
        Verifies that all the sizes and running total match and everything.
        MessageParsingError raised if the messages don't match.
        DumpMessage objects stored in self.dm_list,
        Concatenated payload memoryview in self.data

        message_seq = an iterable of mido messages
        verbose = print status messages to stderr.
        """
        self.dm_list = []

        run = 0
        dmessages = (DumpMessage(msg) for msg in message_seq)

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
                raise MessageSequenceError("Section mismatch")
            if dm.run != run:
                raise MessageSequenceError("Running count mismatch")
            run += dm.padded_size
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
        # end of section
        if verbose:
            count += 1
            eprint("Message {:>{cl}} of {}, end of section".format(
                count, expected_count, cl=count_len, rl=run_len))

        self.dm_list.append(dm)

    def iter_messages(self):
        for dm in self.dm_list:
            yield dm.message

    @lazy_readonly_property('_data')
    def data(self):
        return memoryview(
                b''.join(dm.payload for dm in self.dm_list if dm.payload))
