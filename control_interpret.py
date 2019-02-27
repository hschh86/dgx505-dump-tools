"""
control_interpret.py

Reads a stream of mido text, or an smf file, prints out an interpetation of the
control messages. Optionally, can annotate
"""


import argparse
import logging
import sys

import mido

from commons import util, mido_util
from commons.messages import controlstate

argparser = argparse.ArgumentParser(
    description="Print out an interpretation of the control messages.")

argparser.add_argument(
    'filename', type=str,
    help="file to read from")

argparser.add_argument(
    '-a', '--annotate', action='store_true',
    help="Interpretation as comments on midotext")

argparser.add_argument(
    '-n', '--notes', action='store_true',
    help="Interpret note events as well")

argparser.add_argument(
    '-s', '--smf', type=int, nargs='*', metavar='TRACK', default=None,
    help='Read file as a Standard Midi File instead of midotext. '
         'Optionally, specify the tracks to read')


def state_write(messages, output_stream, wrap_notes, annotate):
    stator = controlstate.MidiControlState(wrap_notes=wrap_notes)
    if annotate:
        for message in messages:
            wrapped = stator.feed(message)
            if message.is_meta:
                # Since meta messages cannot be parsed from midotext,
                # we preface them with a comment
                output_stream.write('#')
            output_stream.write(str(message))
            if wrapped is not None:
                output_stream.write(' # ')
                output_stream.write(str(wrapped))
            output_stream.write('\n')
            output_stream.flush()
    else:
        for message in messages:
            wrapped = stator.feed(message)
            if wrapped is not None:
                output_stream.write(str(wrapped)+'\n')
                output_stream.flush()


def message_time_accumulate(messages, tempo_reset=False):
    # Accumulates the time on the messages.
    t = 0
    for m in messages:
        t += m.time
        # We copy instead of mutating.
        yield m.copy(time=t)
        if tempo_reset and m.type == 'set_tempo':
            t = 0


if __name__ == '__main__':
    args = argparser.parse_args()

    # set up logger
    logger = logging.getLogger('control_interpret')
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    if args.smf is None:
        # smf not provided, read as midotext  
        with util.open_file_stdstream(args.filename, 'rt') as infile:
            try:
                state_write(
                    messages=mido_util.readin_strings(infile, comment='#'),
                    output_stream=sys.stdout,
                    wrap_notes=args.notes,
                    annotate=args.annotate
                )
            except KeyboardInterrupt:
                logger.info("Stopping on KeyboardInterrupt")
    else:
        # smf specified.
        # We don't want negative track numbers.
        for x in args.smf:
            if x < 0:
                raise ValueError(x)

        # Read in the midi file.
        with util.open_file_stdstream(args.filename, 'rb') as infile:
            smf = mido.MidiFile(file=infile)

        if len(args.smf) == 0:
            # No tracks specified, read from all tracks.
            # Mido uses the time attribute as the delta in seconds 
            # when iterating over the file.
            # If we are printing the annotation, we want to accumulate this
            # but if we aren't then we don't care about the time attribute
            # at all.
            messages = iter(smf)
            if args.annotate:
                messages = message_time_accumulate(messages)
        else:
            # Tracks specified.
            track_numbers = sorted(set(args.smf))  # remove duplicates

            # We can treat type 0 and type 2 as the same for this.
            tracks = [smf.tracks[x] for x in track_numbers]
            if smf.type == 1:
                if args.annotate:
                    # We want proper timings. For this purpose,
                    # we use a new MidiFile object.
                    subsmf = mido.MidiFile(
                        type=1,
                        ticks_per_beat=smf.ticks_per_beat,
                        charset=smf.charset)
                    if track_numbers[0] != 0:
                        # Time track not included.
                        # We need to find all the tempo change messages
                        # in track 0, and create a new track
                        # with only them on it.
                        time_track = smf.tracks[0]
                        tempo_track = subsmf.add_track()
                        tempo_track.extend(message_time_accumulate(
                            time_track, tempo_reset=True))
                    # Now we add the other tracks.
                    # (Mutating the 'tracks' list in mido.MidiFile here)
                    subsmf.tracks.extend(tracks)
                    messages = iter(subsmf)
                else:
                    # We don't care about time.
                    # Just combine the tracks.
                    messages = mido.merge_tracks(tracks)
            else:  # type 0 or 2
                if len(tracks) > 1:
                    # If SMF type 0, we shouldn't get here, because there
                    # should be only one track, and we would have errored
                    # beforehand.
                    # If SMF type 2, then we should raise error,
                    # because tracks are not synchronised.
                    raise ValueError("Only one track can be specified for this SMF type")
                if args.annotate:
                    # We care about time.
                    subsmf = mido.MidiFile(
                        type=0,
                        ticks_per_beat=smf.ticks_per_beat,
                        charset=smf.charset)
                    subsmf.tracks.extend(tracks)
                    messages = iter(subsmf)
                else:
                    messages = tracks[0]
        # Now we have the messages, we just write out.
        state_write(
            messages=messages,
            output_stream=sys.stdout,
            wrap_notes=args.notes,
            annotate=args.annotate
        )

            


    








