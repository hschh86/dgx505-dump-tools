"""
slurpECL.py

Honestly there's not much practical use for this one but it was fun to
experiment with.

It's like slurp.py, but sends a midi START message followed by
midi CLOCK messages for the designated tempo, and stops when a midi STOP
message is recieved (or KeyboardInterrupt).

Note that for this to work properly the DGX-505 needs to be set
with EXTERNAL CLOCK = ON. It also won't capture everything needed for
proper playback, because the some of the channel settings are output
when the song/style is selected, not when playback starts, and of course
the tempo cannot change.
"""

import argparse
import mido
import time
import threading
import sys
import logging

from commons import mido_util
from commons.timers import offsetTimer

argparser = argparse.ArgumentParser(
    description="Dumps midi messages as mido text with line breaks to stdout")

argparser.add_argument(
    '-p', '--port', type=str, metavar='PORT',
    help="Input port to read from (run 'mido-ports' to list available ports)")

inportargs = argparser.add_mutually_exclusive_group()
inportargs.add_argument(
    '-g', '--guessport', action='store_true',
    help="Guess which ports to use (partial name match on PORT)")
inportargs.add_argument(
    '-V', '--virtual', action='store_true',
    help='Use virtual ports')

argparser.add_argument(
    '-o', '--outport', type=str, metavar='PORT',
    nargs='?', const=None, default=False,  # a bit hacky but whatever
    help="Use this different output port")

argparser.add_argument(
    '-t', '--tempo', type=float, default='92',
    help="tempo, quarter-notes-per-minute, default 92 qnpm")

argparser.add_argument(
    '-c', '--clocktime', action='store_true',
    help="Use the clock (since epoch) time instead of elapsed time")

args = argparser.parse_args()

input_port = args.port
if args.outport is False:
    output_port = args.port
else:
    output_port = args.outport


CLOCK = mido.Message('clock')
START = mido.Message('start')
STOP = mido.Message('stop')

# midi beat clock is 24 pulses per QN.
# tempo is given in QN per minute
# so the pulse duration in seconds is:
pulse_duration = 60 / (24 * args.tempo)


def new_callback(stopper, clocktime=False):
    # this is a bit of an overcomplicated way to do it but whatever
    if clocktime:
        timer = time.time
    else:
        timer = offsetTimer()

    def msg_callback(message):
        # mutate the message!
        message.time = timer()
        # write text to stdout. Also add a line break
        sys.stdout.write(str(message)+'\n')
        sys.stdout.flush()
        # just a simple conditional
        if message.type == 'stop':
            stopper.set()

    return msg_callback

logger = logging.getLogger('slurpECL')
handler = logging.StreamHandler()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

with mido_util.open_output(
        output_port, args.guessport, args.virtual,
        autoreset=True) as outport:
    logger.info('Sending to port %r', outport.name)
    stopper = threading.Event()
    with mido_util.open_input(
            input_port, args.guessport, args.virtual,
            callback=new_callback(stopper, args.clocktime)) as inport:
        logger.info('Reading from port %r', inport.name)
        # send the start message.
        try:
            outport.send(START)
            while (not stopper.is_set()):
                # MIDI beat clock
                outport.send(CLOCK)
                stopper.wait(pulse_duration)
        except KeyboardInterrupt:
            pass
        finally:
            outport.send(STOP)
