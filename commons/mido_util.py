"""
mido_util.py

utilities for working with mido ports and messages
"""
import logging
import contextlib

import mido
import mido.ports

from . import util


def guess_portname(fragment, portlist):
    """
    iterate over all names in portlist and return the first that has fragment
    as a substring of its name
    Raises ValueError if not found
    """
    for port in portlist:
        if fragment in port:
            return port
    raise ValueError('Unable to guess port from {!r}'.format(fragment))


def open_input(name=None, guess=False, virtual=False, *args, **kwargs):
    """
    Wrapper around mido.open_input, that has an option to guess the name
    from a substring.
    """
    if (name is not None) and (not virtual) and guess:
        name = guess_portname(name, mido.get_input_names())
    return mido.open_input(name, virtual, *args, **kwargs)


def open_output(name=None, guess=False, virtual=False, *args, **kwargs):
    """
    Wrapper around mido.open_output, that has an option to guess the name
    from a substring.
    """
    if (name is not None) and (not virtual) and guess:
        name = guess_portname(name, mido.get_output_names())
    return mido.open_output(name, virtual, *args, **kwargs)


def grab_sysex_until_clock(port):
    """
    generator/filter thing over an iterable of mido messages,
    such as mido ports.
    Discards all messages before the first SysEx,
    then yields all the SysEx messages until a Clock message is sent.
    """
    # discard messages until first sysex
    for message in port:
        if message.type == 'sysex':
            yield message
            break
    # yield messages until next clock
    for message in port:
        if message.type == 'sysex':
            yield message
        elif message.type == 'clock':
            break


def writeout_hex(outfile, messages):
    """
    Write messages as hexadecimal to a (text-mode) file object,
    one message per line.
    Similar to mido.write_syx_file with plaintext=True,
    except uses a file object and doesn't care what type of messages they are
    """
    for message in messages:
        outfile.write(message.hex())
        outfile.write('\n')


def writeout_bytes(outfile, messages):
    """
    Write messages as bytes to a (binary-mode) file object,
    one message per line.
    Similar to mido.write_syx_file with plaintext=False,
    except uses a file object and doesn't care what type of messages they are
    """
    for message in messages:
        outfile.write(message.bin())


def readin_bytes(infile):
    """
    Read in messages from a binary mode file object.
    Returns iterator over Messages.
    """
    data = infile.read()
    parser = mido.Parser()
    parser.feed(data)
    return iter(parser)


def readin_strings(infile):
    """
    Read in string-encoded messages separated by line from a text mode file
    object. Similar to mido.parse_string_stream, except doesn't deal with the
    exceptions.
    Generator, yields messages lazily.
    """
    for line in infile:
        yield mido.parse_string(line)


def read_syx_file(infile):
    """
    Read in a binary or hex syx file.
    Takes a binary mode file object.
    (like mido.read_syx_file, but uses file objects)
    Returns iterator over mido Messages
    """
    data = infile.read()
    parser = mido.Parser()
    if data[0] == 0xF0:
        parser.feed(data)
    else:
        # get rid of non-space whitespace
        text = data.translate(None, b'\t\n\r\f\v').decode('latin1')
        parser.feed(bytes.fromhex(text))
    return iter(parser)


# this was probably a bad idea
def read_syx_file_gen(infile, n=1024):
    parser = mido.Parser()
    data = infile.read1(n)
    if data[0] == 0xF0:
        while data:
            parser.feed(data)
            yield from parser
            data = infile.read1(n)
    else:
        line = data + infile.readline()
        while line:
            text = line.translate(None, b'\t\n\r\f\v').decode('latin1')
            parser.feed(bytes.fromhex(text))
            yield from parser
            line = infile.readline()


# read in messages
@contextlib.contextmanager
def read_messages_file(filename, mfile=False, log=__name__):
        logger = logging.getLogger(log)
        # if args.sfile or args.mfile:
        if mfile:
            file_form = "midotext"
            file_mode = "rt"
            mfunc = readin_strings
        else:  # args.sfile
            file_form = "syx"
            file_mode = "rb"
            mfunc = read_syx_file
        if filename == '-':
            # stdin
            # Needs EOF.
            # to do it better, we could do it asynchronously somehow
            file_display = "stdin"
            file_context = util.nonclosing_stdstream(file_mode)
        else:
            file_display = "file {!r}".format(filename)
            file_context = open(filename, file_mode)
        logger.info("Reading %s from %s", file_form, file_display)
        with file_context as infile:
            yield mfunc(infile)
            logger.info("All messages read from %s", file_display)
