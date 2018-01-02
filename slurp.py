"""
slurp.py

Listens to a port, outputs messages recieved as mido text to stdout.
Uses the mido message object text serialisation.
The 'time' attribute of each message is set to the time elapsed, in seconds,
since listening began. Only approximately, though, so don't rely on it for
proper recording.
"""
import sys
import argparse
import time

from commons import mido_util
from commons.timers import offsetTimer
from commons.util import eprint

argparser = argparse.ArgumentParser(
    description="Dumps midi messages as mido text with line breaks to stdout")

argparser.add_argument(
    '-p', '--port', type=str,
    help="Port to read from (run 'mido-ports' to list available ports)")

portargs = argparser.add_mutually_exclusive_group()
portargs.add_argument(
    '-g', '--guessport', action='store_true',
    help="Guess which port to use (partial name match on PORT)")
portargs.add_argument(
    '-v', '--virtual', action='store_true',
    help='Use virtual port')

argparser.add_argument(
    '-c', '--clocktime', action='store_true',
    help="Use the clock (since epoch) time instead of elapsed time")

args = argparser.parse_args()


# is using the callback-thread thing the right way to do this?
# dunno. super timer accuracy isn't important anyway

def new_callback(clocktime=False):
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

    return msg_callback


with mido_util.open_input(args.port, args.guessport, args.virtual,
                          callback=new_callback(args.clocktime)) as inport:
    eprint('Reading from port {!r}. Press enter to stop'.format(inport.name))
    # wait for any user input
    input()
    # just in case
    inport.callback = None
