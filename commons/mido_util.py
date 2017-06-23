"""
mido_util.py

utilities for working with mido ports and messages
"""
import mido

def get_portname(portname, guess=False):
    """
    Get the name of a mido input port.
    If guess is True, iterate over all port and return the first that
    has portname as a substring of its name
    If guess is False, just return portname
    """
    if guess and portname:
        for port in mido.get_input_names():
            if portname in port:
                return port
        else:
            raise ValueError('Unable to guess port from {!r}'.format(portname))
    else:
        return portname

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
