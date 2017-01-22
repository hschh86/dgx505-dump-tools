# A quick(-ish) overview of the Yamaha DGX-505's Bulk Dump format.
(And probably the DGX-305 as well, but I don't have access to one of those,
so I can't verify)

Acknowledgements to [Robert Hart](http://rnhart.net), who detailed the
Yamaha PSR-225's format [here](http://rnhart.net/articles/bulk-dump.htm).
This page will be using some of the same conventions.

## What's sent over the wire?
When the **Bulk Send** option is selected (see manual p.72),
41 System Exclusive Messages are sent through the instrument's MIDI connection
(over USB, of course).
Other messages, especially the *Clock* messages that are sent constantly when
**External Clock** is set OFF, are not transmitted during this time &mdash;
which means that when you start seeing those, the dump has completed.
(I'm pretty sure Active Sensing is still sent at all times, though.)

The first 38 messages carry the user song data, message 39 signals the end of
that section, message 40 carries the registration memory data, and message 41
signals the end of the messages.

The messages have this general format:
```
F0 43 73 7F 44 06 [tt] [ss ss] [ss ss] [zz zz zz] ([...] [kk]) F7
```
| part                   | length (bytes) | values / explanation      |
|------------------------|----------------|---------------------------|
| status byte            | 1              | `F0`, to signal start of SysEx message |
| header                 | 5              | `43 73 7F 44 06` (This may be slightly different for different  instruments. 43 is the manufacturer ID for Yamaha) |
| type (`t`)             | 1              | `0A` for song data, `09` for registration data |
| full data size (`s`)   | 2              | The number of encoded bytes in the message. (*seven bit representation*) |
| data size? (`s`)       | 2              | The number of encoded bytes in the message, sans padding?? Identical to the size value preceding it in every message except the 40th. (*seven bit representation*) |
| running total (`z`)    | 3              | `7F 7F 7F` indicates the end of section. Otherwise, this is a running total of the number of encoded bytes already in the section so far (*seven bit representation*). |
| data 'payload' (`...`) | up to 2048     | The encoded bytes. Not present if the message is an end-of-section message (39th or 41st) |
| checksum  (`k`)        | 1, if present  | Not present if the messages is end-of-section. Otherwise, this byte is included at the end of the data as a checksum. The sum of all bytes from full data size through checksum inclusive, mod 128, should be zero. |
| status byte            | 1              | `F7`, to signal the end of SysEx message |

**_Seven bit representation_** in the table above refers to the way that the
size and running total values are encoded. As the highest bit of any byte
within the message must be zero, the numbers are encoded seven bits per byte,
with the most significant byte first.
The bytes `08 68`, or 0**0001000**0**1101000** in binary, represent the number
1128, or **00010001101000**, for example.

## Decoding the Data
The data 'payload' is encoded to squish seven eight-bit bytes into eight
effectively-seven-bit bytes, by looking at the data in groups of seven bytes,
taking the highest bit from each and putting them into a new eighth byte after
the seven.

For example, the following sequence of bytes:
> **1**1001001 **0**0001111 **1**1011010 **1**0100010
> **0**0100001 **0**1101000 **1**1000010

when encoded, becomes:

> *0*1001001 *0*0001111 *0*1011010 *0*0100010
> *0*0100001 *0*1101000 *0*1000010 *0*__1011001__

To decode the payload and recover the original data, one must split
into groups of eight bytes, take the eighth and put the seven bits back onto
their original bytes.

One consequence of this is that the length of the encoded data must be a
multiple of eight, and the data after decoding has a length of a multiple of
seven. The original data may not have had such a length, so some padding might
have been included to make it so. I believe this is the reason that there are
two separate values for data length per message (although I can't prove it),
based solely upon the fact the 40th message has two size values that differ by
two, the first of which is the actual length of the encoded data, and its
decoded data has two extra null bytes at the end of it.

## User Song data format
After decoding and concatenating, the data contained in the first 38 messages
consists of 67291 (hex: `106DB`) bytes, the meaning of which, as far as I can
tell, are as follows:

### Songs in use
Offset: `00000`, Length: `1`

The very first byte is a bit array, where the low five bits correspond to the
five user songs. A **1** means the song is in use, a **0** not.
The lowest bit corresponds to the first song, that is:

* `01` = Song 1
* `02` = Song 2
* `04` = Song 3
* `08` = Song 4
* `10` = Song 5

A value of `1A` = 000**11010** would mean that user songs 2, 4, and 5 are in
use, for example.

### Mystery Region
Offset: `00001`, Length: `15C`

Then follows 348 bytes of I don't know what. I think this has something to do
with the 'file system' or flash memory management or statistics or something,
but it doesn't seem to be that important in terms of song data.

### Tracks in use
Offset: `0015D`, Length: `1` &times; 5

The five bytes at offsets `0015D` through `00161` are the bit arrays
for the recorded tracks in user songs 1 through 5 respectively.

* `01` = Track 1 (right)
* `02` = Track 2 (left)
* `04` = Track 3
* `08` = Track 4
* `10` = Track 5
* `20` = Track A (Style/Chord track)

For example, if the byte at offset `0015E` had value `29` = 00**101001**,
that would mean that User Song 2 had tracks 1, 4, and A recorded.

### Five Bytes of Nothing
Offset: `00162`, Length: `5`

There are five zero bytes here, which I suspect were intended for
a feature that the DGX-505 doesn't have.

### Song Durations
Offset: `00167`, Length: `4` &times; 5

At offsets `00167`, `0016B`, `0016F`, `00173`, `00177` are the durations
in measures/bars of the user songs 1-5 respectively, as what appears to be
big-endian 32-bit integers. The size certainly seems like overkill.
If a song is not in use, its duration is zero.

### Track Durations
Offset: `0017B`, Length: (`4` &times; 6) &times; 5

Immediately after the song durations follow thirty more 32-bit integers
(120 bytes!), the durations of each track, starting from Song 1 Track 1
at `0017B`, Song 1 Track 2 at `0017F` and so on all the way to Song 5 Track A
at `001EF`. Tracks not recorded have zero duration.

### "PresetStyle"
Offset: `001F3`, Length: `C` &times; 5

Then we have the sequence `50 72 65 73 65 74 53 74 79 6C 65 00` repeated five
times. When decoded to ASCII, this reads "PresetStyle" plus a null byte.
(Probably some of those C-style null-terminated strings.)

### Beginning Blocks
Offset: `0022F`, Length: (`1` &times; 6) &times; 5

The 'file system' used to store the song data (as Standard MIDI *MTrk* chunks)
is made up of 130 (hex: `82`) blocks/clusters numbered from `01` to `82`.
The thirty bytes at offsets `0022F` through `0024C` are the numbers of the blocks where the tracks begin.
A value of `FF` means that the track is not in use.

The same order as that of track durations is used, i.e. `0022F`
for Song 1 Track 1, `00230` for Song 1 Track 2, all the way to `0024C` for
Song 5 Track A. For example, the byte at offset `00236` having value `3B`
means Song 2 Track 2's data begins at block `3B`.

Even if a song's Track A was not recorded, the corresponding chunk is still
present &mdash; it's used as the time track.

### Next blocks
Offset: `0024D`, Length: `1` &times; `82`

The blocks in which the tracks are stored are not necessarily adjacent or
contiguous, as tracks are erased, recorded or overwritten, so from `0024D` to
`002CE` there is a table indicating the number of the block to be read next,
like a linked list.
A value of `00` means the block is unused (although it may still contain
remnants of old recordings), and `FF` means that the block is the last block,
the end of the chain.

Each block has its corresponding entry in order, so offset `0024D` has the
number of the block to read next after block `01`, offset `0024E` for
block `02`, and so on up to offset `002CE` for block `82`.

### "PK0001"
Offset: `002CF`, Length: `6`

The six bytes `50 4B 30 30 30 31`, ASCII for "PK0001", mark the beginning of
the data blocks.

### Block Data
Offset: `002D5`, Length: `200` &times; `82`

Offset `002D5` marks the start of the first 512-byte block.
There are 130 of them.

To calculate the start of each block we can use a simple formula
```
offset(n) = 0x2d5 + (0x200 * (n-1))
```
or, to simplify,
```
offset(n) = 0xd5 + (0x200 * n)
```

### The End
Offset: `106D5`, Length: `6`

After all 66560 bytes of data, another "PK0001" marks the end.

## User Song MIDI
### The Time track and proprietary (meta-)events (WIP)
In addition to storing the style and chord information (as proprietary SysEx
and meta-events) from Track A, the time track also contains the time signature
and tempo meta-events (and a bunch of other things).
For this reason, the time track is present for all songs in use whether Track
A is recorded or not.

*The meta-events seem to be similar to those of the PSR-225 with the exception
of the chord meta-events (especially the chord root byte)*

#### SysEx events (see also manual p.111)
##### GM System On
`F0 7E 7F 09 01 F7`

##### Reverb Type
`F0 43 15 4C 02 01 00 mm ll F7`

* `mm` = MSB
* `ll` = LSB

##### Chorus Type
`F0 43 15 4C 02 01 20 mm ll F7`

* `mm` = MSB
* `ll` = LSB

#### Proprietary Meta-Events
`43 76 1A tt ...`, where `tt` is the type:

* `01` = Section Change
* `02` = Accompaniment Volume
* `03` = Chord
* `04` = Style no.

##### Section Change
`43 76 1A 01 xx`

* `00` = Main A
* `01` =
* `02` = Fill AB
* `03` =
* `04` =
* `05` = Main B
* `06` = Fill BA
* `07` =
* `08` =
* `09` =

*(This one needs more experimentation)*

##### Style Volume?
`43 76 1A 02 vv`

*(Also needs more experimentation)*

##### Chord
`43 71 1A 03 rr tt rr tt`

*Similar to the PSR-225 but the two sets are sometimes
 different and rr is different*

##### Style
`43 71 1A 04 ss ss`

where ss is the style number, minus 1.

*I'm not sure why two bits are needed but maybe there's
byte splitting or something. More experimentation required*

### Extracting the song as a MIDI file
Each track is stored as a Standard MIDI *MTrk* chunk. To create a MIDI file
of, say, User Song 1, this procedure should broadly work:
  1. Read the corresponding bytes from the Beginning Blocks section, which
     should tell you both which tracks are in use and where to start looking
     for the data.
  2. Follow the chain through the Next Blocks section, which should tell you
     which blocks to look at and in which order.
  3. Assemble the blocks in order.
  4. Read the first few bytes from the assembled blocks, enough to read the
     length of the chunk. Then read the rest of the chunk.
     * Don't read too much, or else you'll end up with junk data
       (the leftovers from previous recordings)
  5. Repeat for all the tracks.
  6. Construct a *MThd* chunk and assemble the MIDI file.
     * The format needs to be *Type 1*
     * division = 96 ticks per quarter-note (i.e. `00 60`)
     * The time track goes first.

## Registration (a.k.a. One-Touch-Settings) data format
### Overall Structure
The second-last message, no. 40, contains 816 encoded bytes that decode to 714 bytes, structured roughly as follows.

#### "PSR"
Offset: `000`, Length: `4`

The registration data is book-ended by `50 53 52 03`, the which happens to be
ASCII for "PSR" plus `03` (end-of-text control character?)

#### One-Touch-Settings
Offset: `004`, Length: `2C` &times; 16

The DGX-505 has 8 banks &times; 2 buttons = 16 settings that can be saved.
Each is represented here with 44 (hex: `2C`) bytes.
The settings are organised first by button, then by bank, i.e.
* offset `004` = Button 1, Bank 1
* offset `030` = Button 1, Bank 2
* ...
* offset `138` = Button 1, Bank 8
* offset `164` = Button 2, Bank 1
* ...
* offset `664` = Button 2, Bank 8

#### "PSR"
Offset: `2C4`, Length: `4`

The closing book-end, `50 53 52 03`.

#### Two bytes of padding
Offset: `2C8`, Length: `2`

Then we find `00 00`, which I suspect was added to make the length a multiple
of seven.

### Unpacking Each Setting
Each 44-byte setting has following structure:

#### ??
Offset: `00`, Length: `1`

On all the dumps I've seen, the first byte been the value `01`.
I suspect this may be the flag that records whether the setting is in use,
but there's no way to only erase one setting at a time so I haven't been able
to check.
(I'm not gonna to erase all the memory, which seems to be the only way to do it)

#### Style number
Offset: `01`, Length: `1`

The style number as displayed on the panel, minus 1 (if present).

 * `00` to `87` = style 001 to 136
 * `FF` = no style was recorded (i.e. it was in song mode).

#### Accompaniment ON/OFF
Offset: `02`, Length: `1`

* `FF` = no style
* `00` = Accompaniment OFF
* `01` = Accompaniment ON

#### Split Point
Offset: `03`, Length: `1`

* `00` to `7F` = 000 (C-2) to 127 (G8) (see manual p.71)

#### Split Point again
Offset: `04`, Length: `1`

Identical to above. Probably here because one is the voice split point and
one is the chord split point, but they're the same setting on the DGX-505.

#### Main A/B
Offset: `05`, Length: `1`

* `FF` = no style
* `00` = Main A
* `05` = Main B

#### Style Volume
Offset: `06`, Length: `1`

* `FF` = no style
* `00` to `7F` = volume 000 to 127

#### Main Voice section
Offset: `07`, Length: `7`

The Main Voice settings:
##### Voice Number
Offset: `0` within voice section (= `07` overall), Length: `2`

Two bytes that represent a big-endian 16-bit integer.
Values run from `0000` to `01ED`, corresponding to voices 001 to 494
(i.e. the value is the panel voice number, minus one).

* `0000` to `01ED` = voice 001 to 494

##### Octave
Offset: `2` within voice section, Length: `1`

* `FE` to `02` = octave -2 to +2 (twos complement for negatives)

##### Volume
Offset: `3` within voice section, Length: `1`

* `00` to `7F` = volume 000 to 127

##### Pan
Offset: `4` within voice section, Length: `1`

* `00` to `7F` = pan 000 (left) to 127 (right) (see manual p.71)

##### Reverb Send Level
Offset: `5` within voice section, Length: `1`

* `00` to `7F` = reverb level 000 to 127

##### Chorus Send Level
Offset: `6` within voice section, Length: `1`

* `00` to `7F` = chorus level 000 to 127

#### Split ON/OFF
Offset: `0E`, Length: `1`

* `00` = Split OFF
* `7F` = Split ON

#### Split Voice section
Offset: `0F`, Length: `7`

*See Main Voice section for detail*

#### Dual ON/OFF
Offset: `16`, Length: `1`

* `00` = Dual OFF
* `7F` = Dual ON

#### Dual Voice section
Offset: `17`, Length: `7`

*See Main Voice section for detail*

#### Pitch Bend Range
Offset: `1E`, Length: `1`

* `01` to `0C` = range 01 to 12

#### Reverb Type
Offset: `1F`, Length: `1`

* `01` to `0A` = reverb type 01 to 10, see manual p.71 & p.109

There are also some settings that cannot be selected using the panel and must
be chosen by sending MIDI messages (the numberless ones on p.113), which are
saved using these values:

* `0B` = Room
* `OC` = Stage
* `OD` = Plate

#### Chorus Type
Offset: `20`, Length: `1`

* `01` to `05` = chorus type 01 to 05, see manual p.71 & p.109

Like Reverb Type, Chorus Type also has 'extra' settings:

* `06` = Thru
* `O7` = Chorus
* `O8` = Celeste
* `09` = Flanger

#### Harmony ON/OFF
Offset: `21`, Length: `1`

* `00` = Harmony OFF
* `7F` = Harmony ON

#### Harmony Type
Offset: `22`, Length: `1`

* `01` to `1A` = harmony type 01 to 26, see manual p.71 & p.108

#### Harmony Volume
Offset: `23`, Length: `1`

* `00` to `7F` = volume 000 to 127

#### ??
Offset: `24`, Length: `1`

This always seems to be `FF`. Don't know if it means anything

#### Transpose
Offset: `25`, Length: `1`

The value stored here is the panel value plus 12
(so that -12 is 0 and +12 is 24)

* `00` to `18` = -12 to +12

#### Tempo
Offset: `26`, Length: `1`

The tempo is stored as the panel value minus 32

* `FF` = no style
* `00` to `F8` = 32 bpm to 280 bpm

#### ??
Offset: `27`, Length: `2`

Two zero bytes.

#### Panel Sustain
Offset: `29`, Length: `1`

This one uses weird values for ON and OFF. Dunno why.

* `40` = Sustain OFF
* `6E` = Sustain ON

#### ??
Offset: `2A`, Length: `2`

Two more zero bytes.
