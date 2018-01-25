"""
broadcast.py

Basically, the opposite of slurp.py.
Keep in mind that the times are only approximate
"""
import time
import argparse
import operator
import logging

from commons import util, mido_util

argparser = argparse.ArgumentParser(
    description="Dumps contents of a text mido message stream file "
                "to a midi port. "
                "Time attribute = time elapsed in seconds")

portargs = argparser.add_mutually_exclusive_group()
portargs.add_argument(
    '-g', '--guessport', action='store_true',
    help="Guess which port to use (partial name match on PORT)")
portargs.add_argument(
    '-V', '--virtual', action='store_true',
    help='Use virtual port')

argparser.add_argument(
    '-p', '--port', type=str,
    help="Port to write to (run 'mido-ports' to list available ports)")
argparser.add_argument(
    '-s', '--speedup', type=float, default='1',
    help="speed multiplier")
argparser.add_argument(
    '-c', '--clockless', action='store_true',
    help="ignore clock messages when reading")


waitgroup = argparser.add_mutually_exclusive_group()
waitgroup.add_argument(
    '-n', '--nowait', action='store_true',
    help='Ignore the first time attr, stream out with no initial delay')
waitgroup.add_argument(
    '-i', '--ignoretime', action='store_true',
    help='Ignore all time attrs, just stream out messages as fast as possible,'
         ' i.e. 3125 bytes/second-ish. Can be sped up using speedup argument')

argparser.add_argument(
    '--prompt', action='store_true',
    help='prompt before playback')

argparser.add_argument(
    'filename', type=str,
    help="file to read from")


DEFAULT_BYTERATE = 3125


def ignore_time_deltas(msg_list, bytewait):
    yield (0, msg_list[0])
    for last, msg in util.iter_pairs(msg_list):
        wait = len(last)*bytewait
        yield (wait, msg)


def use_time_deltas(msg_list, nowait, speedup):
    msg = msg_list[0]
    if speedup <= 0:
        raise ValueError("Speedup must be positive!")
    if nowait or (msg.time < 0):
        wait = 0
    else:
        wait = msg.time / speedup
    yield (wait, msg)
    for last, msg in util.iter_pairs(msg_list):
        # just completely ignore the bytewait?
        wait = (msg.time - last.time)/speedup
        yield (wait, msg)


def main(args):
    logger = logging.getLogger('broadcast')

    with util.open_file_stdstream(args.filename, 'rt') as infile:
        # blocking read
        msg_gen = mido_util.readin_strings(infile)
        if args.clockless:
            msg_gen = (msg for msg in msg_gen if msg.type != 'clock')
        msgs = list(msg_gen)

    # open the port.
    with mido_util.open_output(
            args.port, args.guessport, args.virtual) as outport:

        # bytewait
        if args.speedup > 0:
            bytewait = 1/(DEFAULT_BYTERATE*args.speedup)
        else:
            bytewait = 0

        # sort messages by time, just in case.
        msgs.sort(key=operator.attrgetter('time'))

        # compute the deltas.
        if args.ignoretime:
            dmt = ignore_time_deltas(msgs, bytewait)
        else:
            dmt = use_time_deltas(msgs, args.nowait, args.speedup)
        delta_message_tuples = list(dmt)

        # send the messages.
        try:
            logger.info("sending to port %r", outport.name)
            if args.prompt:
                input("Press enter to start")
            for wait, msg in delta_message_tuples:
                time.sleep(wait)
                outport.send(msg)
            time.sleep(len(msg)*bytewait)
            logger.info("finished")
        except KeyboardInterrupt:
            # newline, as to not screw up the prompt
            print()
        finally:
            # I've found that when using a2jmidid
            # the port can close too early for autoreset to work
            # so here we reset manually and sleep before actually closing
            outport.reset()
            time.sleep(0.1)


if __name__ == '__main__':
    args = argparser.parse_args()

    # set up logger
    logger = logging.getLogger('broadcast')
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    main(args)
