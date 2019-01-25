"""
control_interpret.py

A bit of an experiment.

It's like slurp, except we only look for and interpret the controls.
Also doesn't give mfile compatible output.
"""


import argparse
import logging

from commons import mido_util
from commons.messages import controlstate

argparser = argparse.ArgumentParser(
    description="Print out an interpretation of the control messages.")
argparser.add_argument(
    'input', type=str,
    help="Port to read from (run 'mido-ports' to list available ports)"
         " / Filename if applicable")

ingroup = argparser.add_argument_group("Input options")
inargs = ingroup.add_mutually_exclusive_group()
inargs.add_argument(
    '-g', '--guessport', action='store_true',
    help="Guess which port to use (partial name match on PORT)")
inargs.add_argument(
    '-V', '--virtual', action='store_true',
    help='Use virtual port')
inargs.add_argument(
    '-f', '--mfile', action='store_true',
    help="Read from mido message text file instead of port")

argparser.add_argument(
    '-q', '--quiet', action='store_true',
    help="Don't print progress messages to stderr")



if __name__ == '__main__':
    args = argparser.parse_args()

    # set up logger
    logger = logging.getLogger('control_interpret')
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    if args.quiet:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)

    stator = controlstate.MidiControlState()

    if args.mfile:
        message_source = mido_util.read_messages_file(
            args.input, mfile=True, log='control_interpret')
    else:
        message_source = mido_util.open_input(
            args.input, args.guessport, args.virtual)
    
    with message_source as inport:
        for message in inport:
            output = stator.feed_message(message)
            if output is not None:
                print(output)