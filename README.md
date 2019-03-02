# dgx505-dump-tools

A collection of scripts for dealing with the bulk dump data from a Yamaha DGX-505.
Uses the [mido library](https://pypi.python.org/pypi/mido/), and a suitable backend
such as [rtmidi-python](https://pypi.python.org/pypi/python-rtmidi/).

## Documents

Some documents and experiments with the MIDI can be found in the documents directory.

 - Information about the MIDI as implemented by the Yamaha DGX-505 is found in the [DGX505Midi](./documents/DGX505Midi.md) document.

 - Information about the specific format of the Bulk Dump messages is found in the [BulkDumpFormat](./documents/BulkDumpFormat.md) document.

## Scripts

Haphazardly disorganised in the top-level of this directory are a collection of scripts. Each of these depends on the 'library' formed in the `commons` directory.

### `collect.py` and `extractor.py`

`collect.py` is used to record the bulk dump messages sent from the DGX-505 to a file
(it just writes to standard output, so use the shell to save).

`extractor.py` is used to extract information from the bulk dump file.
The bulk dumps contain information about the recorded User Songs and registration bank
data, which can be read by `extractor.py`. The User Songs can also be output as 
standard MIDI files (although any accompaniment will not be present, and the octave
of some notes may be wrong, see [BulkDumpFormat](./documents/BulkDumpFormat.md) document
for more details).

### `slurp.py`, `broadcast.py`, and `control_interpret.py`

These scripts are used to record MIDI messages for experimentation, in a very simple
format we refer to as "midotext" (which is pretty much just the default Mido text
serialisation for MIDI messages).

It can be recorded from a MIDI port with `slurp.py` and played back over a MIDI port with `broadcast.py`. Midotext files can be used as input for `collect.py` and
`extractor.py` as well.

`control_interpret.py` can be used to annotate the messages with somewhat more helpful
descriptions, mostly putting names to the controller change numbers and system exclusive
messages that are supported by the DGX-505.

### `slurpECL.py` and `slurp_rtmidi.py`

These are experiments that basically do the same thing as `slurp.py`, but in slightly
different ways. Not very useful, will probably be removed.

