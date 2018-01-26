"""
slurp.py

Listens to a port, outputs messages received as mido text to stdout.
Uses the mido message object text serialisation.
The 'time' attribute of each message is set to the time elapsed, in seconds,
since listening began. Only approximately, though, so don't rely on it for
proper recording.
"""
import sys
import argparse
import time
import logging

from commons import mido_util
from commons.timers import offsetTimer

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
    '-V', '--virtual', action='store_true',
    help='Use virtual port')

argparser.add_argument(
    '-c', '--clocktime', action='store_true',
    help="Use the clock (since epoch) time instead of elapsed time")

argparser.add_argument(
    '-q', '--quiet', action='store_true',
    help="Don't print progress messages to stderr")


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


def main(args):
    logger = logging.getLogger('slurp')
    with mido_util.open_input(args.port, args.guessport, args.virtual,
                              callback=new_callback(args.clocktime)) as inport:
        try:
            logger.info('Reading from port %r. Press enter to stop',
                        inport.name)
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
            inport.callback = None


if __name__ == '__main__':
    args = argparser.parse_args()

    # set up logger
    logger = logging.getLogger('slurp')
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    if args.quiet:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)

    main(args)
