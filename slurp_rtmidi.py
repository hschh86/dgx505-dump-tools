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
import time

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

argparser.add_argument(
    '-P', '--poll', type=float, nargs='?', default=None, const=0.25,
    help="Use polling instead of callback. "
         "Optionally specify interval, in seconds, default is 0.25")

argparser.add_argument(
    '-q', '--quiet', action='store_true',
    help="Don't print progress messages to stderr")


def new_callback():
    # Note the difference between this callback and the one in slurp.py,
    # which counts the time elapsed since the callback was created;
    # this one counts the time since the first message received.
    acc = 0

    def rtmidi_callback(msg_delta, data=None):
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
    """
    Open an input port on the instance rt.
    Returns the name of the port.
    """
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


def flush_messages(rt, callback):
    # deal with the callback manually.
    # probably neater to rework everything into a class instead of
    # throwing rt and callback around all the time, but hey, it works.
    while True:
        msg_delta = rt.get_message()
        if msg_delta is None:
            # no messages, return
            return
        else:
            callback(msg_delta)


def main(args):
    logger = logging.getLogger('slurp_rtmidi')

    # create the MidiIn instance.
    rt = rtmidi.MidiIn()
    # here, we're just using the default API because I don't care that much.
    # However, it may be useful to read from the mido settings.

    # By default, sysex, clock, and active sense messages are ignored.
    # we only want to ignore active sense.
    rt.ignore_types(sysex=False, timing=False, active_sense=True)

    # create the callback
    callback = new_callback()
    # Callback or poll?
    if args.poll is None:
        # set the callback.
        rt.set_callback(callback)
    else:
        # we're going to be polling the interval,
        # calling the callback ourselves.
        if args.poll <= 0:
            raise ValueError("Polling interval must be positive")

    # Now we need to open the port.
    port_name = open_input(rt, args.port, args.guessport, args.virtual)

    try:
        logger.info('Reading from port %r. CtrlC to stop',
                    port_name)
        if args.poll is None:
            # we've set the callback, so we just sleep
            while True:
                time.sleep(300)
        else:
            # we need to poll.
            while True:
                flush_messages(rt, callback)
                time.sleep(args.poll)
    except KeyboardInterrupt:
        # ctrl-c
        logger.info('Stopping on KeyboardInterrupt')
    finally:
        # close the port. (Also cancels the callback)
        rt.close_port()
        # Deal with the remaining messages
        flush_messages(rt, callback)
        # note: virtual ports don't actually close until rt is deleted
        # so there is the possibility that messages keep coming in.
        # It is then possible that we can't handle them fast enough,
        # so flush_messages keeps running forever.
        # in that case, we'd need to interrupt again.
        del rt
        # It seems that when the message buffer fills up, an error
        # message is just printed to stderr,
        # with no (reasonable) way to catch it.


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
