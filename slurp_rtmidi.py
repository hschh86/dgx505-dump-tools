"""
slurp_rtmidi.py

Listens to a port, outputs messages received as mido text to stdout.
Uses the mido message object text serialisation.

Like slurp.py, but uses python-rtmidi directly, because I want to make use
of the rtmidi's timestamp slightly more directly.
"""
import sys
import argparse
import logging

import mido
import rtmidi

from commons import mido_util

argparser = argparse.ArgumentParser(
    description="Dumps midi messages as mido text with line breaks to stdout")

argparser.add_argument(
    '-p', '--port', type=str,
    help="Port to read from")

portargs = argparser.add_mutually_exclusive_group()
portargs.add_argument(
    '-g', '--guessport', action='store_true',
    help="Guess which port to use (partial name match on PORT)")
portargs.add_argument(
    '-V', '--virtual', action='store_true',
    help='Use virtual port')
#
# argparser.add_argument(
#     '-c', '--clocktime', action='store_true',
#     help="Use the clock (since epoch) time instead of elapsed time")

argparser.add_argument(
    '-q', '--quiet', action='store_true',
    help="Don't print progress messages to stderr")


def new_callback():
    acc = 0

    def rtmidi_callback(msg_delta, data):
        nonlocal acc
        # Use this as the callback, which runs in the rtmidi input thread.
        # (I think.)
        msg_bytes, delta_time = msg_delta
        # delta_time is seconds elapsed since last message.
        # If i'm reading through the rtmidi source correctly,
        # the first message has a timestamp of 0.0
        acc += delta_time
        # considering that the timestamps only appear to have a precision
        # of around six decimal places, the floating-point errors from
        # adding up all the deltas like this shouldn't matter
        try:
            msg = mido.Message.from_bytes(msg_bytes, time=acc)
        except ValueError:
            # like mido, we just ignore invalid messages
            # (we've already added the accumulator)
            pass
        else:
            # write text to stdout. Also add a line break
            sys.stdout.write(str(msg)+'\n')
            sys.stdout.flush()

    return rtmidi_callback


def open_input(rt, name, guess, virtual):

    if virtual:
        # Open a virtual port.
        rt.open_virtual_port(name)
        return name
    else:
        # Open a non-virtual port.
        # First we need the port names
        port_names = rt.get_ports()
        if name is None:
            # For the default
            # we just take the first one, thanks.
            port_name = port_names[0]
            port_number = 0
        else:
            # We need to figure out the proper name...
            if guess:
                port_name = mido_util.guess_portname(name, port_names)
            else:
                # mido does clever things to get around the ALSA names
                # we don't care, because I'm lazy and we can guess anyway
                port_name = name
            # Then, we find the corresponding number
            # ... it just occurred to me that this is vulnerable to
            # race conditions. oh well nothing we can do about it
            port_number = port_names.index(port_name)
        # Then, actually open the non-virtual port.
        rt.open_port(port_number)
        return port_name


def main(args):
    logger = logging.getLogger('slurp_rtmidi')

    # create the MidiIn instance.
    rt = rtmidi.MidiIn()
    # here, we're just using the default API because I don't care that much.
    # However, it may be useful to read from the mido settings.

    # By default, sysex, clock, and active sense messages are ignored.
    # we only want to ignore active sense.
    rt.ignore_types(sysex=False, timing=False, active_sense=True)

    # create and set the callback.
    rt.set_callback(new_callback())
    # Note the difference between this callback and the one in slurp.py,
    # which counts the time elapsed since the callback was created;
    # this one counts the time since the first message received.

    # Now we need to open the port.
    port_name = open_input(rt, args.port, args.guessport, args.virtual)

    try:
        logger.info('Reading from port %r. Press enter to stop',
                    port_name)
        # wait for any user input
        input()
    except KeyboardInterrupt:
        # ctrl-c
        logger.info('Stopping on KeyboardInterrupt')
    except EOFError:
        # ctrl-d or eof if a file is piped in for some reason
        logger.info('Stopping on input EOF')
    else:
        # input on stdin
        logger.info('Stopping on input')
    finally:
        # just in case
        del rt


if __name__ == '__main__':
    args = argparser.parse_args()

    # set up logger
    logger = logging.getLogger('slurp_rtmidi')
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    if args.quiet:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)

    main(args)
