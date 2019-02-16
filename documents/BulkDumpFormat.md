# An overview of the Yamaha DGX-505's Bulk Dump format.

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
**External Clock** is set OFF, are not transmitted during this time —
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

Offset: `0015D`, Length: `1` × 5

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

Offset: `00167`, Length: `4` × 5

At offsets `00167`, `0016B`, `0016F`, `00173`, `00177` are the durations
in measures/bars of the user songs 1-5 respectively, as what appears to be
big-endian 32-bit integers. The size certainly seems like overkill.
If a song is not in use, its duration is zero.

I *think* these are the durations, but weird things seem to happen to the numbers when the time signature is changed for newly recorded tracks, so don't rely on these too much.


### Track Durations

Offset: `0017B`, Length: (`4` × 6) × 5

Immediately after the song durations follow thirty more 32-bit integers
(120 bytes!), the durations of each track, starting from Song 1 Track 1
at `0017B`, Song 1 Track 2 at `0017F` and so on all the way to Song 5 Track A
at `001EF`. Tracks not recorded have zero duration.


### "PresetStyle"

Offset: `001F3`, Length: `C` × 5

Then we have the sequence `50 72 65 73 65 74 53 74 79 6C 65 00` repeated five
times. When decoded to ASCII, this reads "PresetStyle" plus a null byte.
(Probably some of those C-style null-terminated strings.)

This region is zeroed out when the memory is cleared and no songs have been
recorded, so it's probably something to do with the five songs.


### Beginning Blocks

Offset: `0022F`, Length: (`1` × 6) × 5

The 'file system' used to store the song data (as Standard MIDI *MTrk* chunks)
is made up of 130 (hex: `82`) blocks/clusters numbered from `01` to `82`.
The thirty bytes at offsets `0022F` through `0024C` are the numbers of the blocks where the tracks begin.
A value of `FF` means that the track is not in use.

The same order as that of track durations is used, i.e. `0022F`
for Song 1 Track 1, `00230` for Song 1 Track 2, all the way to `0024C` for
Song 5 Track A. For example, the byte at offset `00236` having value `3B`
means Song 2 Track 2's data begins at block `3B`.

Even if a song's Track A was not recorded, the corresponding chunk is still
present — it's used as the time track.


### Next blocks

Offset: `0024D`, Length: `1` × `82`

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

Offset: `002D5`, Length: `200` × `82`

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

### The Time track and proprietary (meta-)events

In addition to storing the style and chord information (as proprietary SysEx
and meta-events) from Track A, the time track also contains the time signature
and tempo meta-events (and a bunch of other things).
For this reason, the time track is present for all songs in use whether Track
A is recorded or not.

The Time track contains the master Reverb/Chorus type for the entire song, which seems to be the Reverb/Chorus Type settings recorded for the most recent track.
Recording a new track with different Reverb/Chorus types alters the Reverb/Chorus Type messages at the beginning of this track, too.

Erasing Track A deletes the information about chords but keeps the preliminary information (tempo, Reverb/Chorus type etc).


#### SysEx events (see also manual p.111, and [DGX-505 MIDI document](./DGX505Midi.md))

##### GM System On

`F0 7E 7F 09 01 F7`

This message, in the DGX-505 context, resets the MIDI settings to default (see [DGX-505 MIDI document](./DGX505Midi.md) for more details).


##### Reverb Type

`F0 43 15 4C 02 01 00 mm ll F7`

* `mm` = MSB
* `ll` = LSB

(see [DGX-505 MIDI document](./DGX505Midi.md).)


##### Chorus Type

`F0 43 15 4C 02 01 20 mm ll F7`

* `mm` = MSB
* `ll` = LSB

(see [DGX-505 MIDI document](./DGX505Midi.md).)


#### Proprietary Meta-Events

Proprietary (Sequencer-Specific) Meta-Events are of format
`FF 7F len data` (see MIDI specs).

For these Yamaha proprietary meta-events, `data`
takes the form `43 76 1A tt ...`, where `tt` is the type:

* `01` = Section Change
* `02` = Style (accompaniment) Volume
* `03` = Chord
* `04` = Style number


##### Section Change

`43 76 1A 01 xx`

* `00` = Main A
* `02` = Fill (A to) B
* `03` = Intro A
* `04` = Ending (A)
* `05` = Main B
* `06` = Fill (B to) A
* `08` = Intro B
* `09` = Ending (B)

Note that `01` and `07` are not supported values for the DGX-505.

Also note that although the message displayed for Ending does not include A or B, different codes are used.
Ending (rit.) does not have its own code, it is a combination of Ending and tempo changes.


##### Style Volume

`43 76 1A 02 vv`

The volume takes values from 0 to 127.


##### Chord

`43 76 1A 03 cr ct bn bt`

The Chord change meta-events have the chord specified by `cr ct bn bt`, where:

* `cr` = Chord root
* `ct` = Chord type
* `bn` = On-bass note
* `bt` = Bass type

(This terminology comes from the Yamaha XF Format specification. I'm not sure if it applies exactly, but it's better than nothing.)

###### Root Notes

For the range of values produced by the DGX-505, the higher bits (first hex digit) specify the type of note:

* `2x` = Flat
* `3x` = Natural
* `4x` = Sharp

while the lower bits (second hex digit) specify the note base name:

* `x1` = C
* `x2` = D
* `x3` = E
* `x4` = F
* `x5` = G
* `x6` = A
* `x7` = B

Thus, the possible chord root values in for each note in chromatic order are:

* `31` = C
* `22` = D♭
* `32` = D
* `23` = E♭
* `33` = E
* `34` = F
* `44` = F♯
* `35` = G
* `45` = G♯
* `36` = A
* `27` = B♭
* `37` = B

There is an additional scheme used alongside the above one for root notes that is not produced by the DGX-505 but is found in the System Exclusive chord change messages in the MIDI files on the supplied CD-ROM.

This scheme simply assigns codes in chromatic order, ignoring enharmonic differences.

* `00` = C
* `01` =
* `02` = D
* `03` =
* `04` = E
* `05` = F
* `06` = F♯
* `07` = G
* `08` =
* `09` = A
* `0A` =
* `0B` = B


###### Chord Type

An example chord with root note C is given in square brackets.
Note that the order is different to that in the manual on p.62).

* `00` = Major [C]
* `01` = Sixth [C6]
* `02` = Major seventh [CM7]
* `03` = Major seventh add sharp eleventh [CM7(♯11)]
* `04` = Add ninth [C(9)]
* `05` = Major seventh ninth [CM7(9)]
* `06` = Sixth ninth [C6(9)]
* `07` = Augmented [Caug]
* `08` = Minor [Cm]
* `09` = Minor sixth [Cm6]
* `0A` = Minor seventh [Cm7]
* `0B` = Minor seventh flatted fifth [Cm7♭5]
* `0C` = Minor add ninth [Cm(9)]
* `0D` = Minor seventh ninth [Cm7(9)]
* `0E` = Minor seventh add eleventh [Cm7(11)]
* `0F` = Minor major seventh [CmM7]
* `10` = Minor major seventh ninth [CmM7(9)]
* `11` = Diminished [Cdim]
* `12` = Diminished seventh [Cdim7]
* `13` = Seventh [C7]
* `14` = Seventh suspended fourth [C7sus4]
* `15` = Seventh flatted fifth [C7♭5]
* `16` = Seventh ninth [C7(9)]
* `17` = Seventh add sharp eleventh [C7(♯11)]
* `18` = Seventh add thirteenth [C7(13)]
* `19` = Seventh flatted ninth [C7(♭9)]
* `1A` = Seventh add flatted thirteenth [C7(♭13)]
* `1B` = Seventh sharp ninth [C7(♯9)]
* `1C` = Major seventh augmented [CM7aug]
* `1D` = Seventh augmented [C7aug]
* `1E` = Octave [C1+8]
* `1F` = Perfect fifth [C1+5]
* `20` = Suspended fourth [Csus4]
* `21` = Suspended second [Csus2]
* `22` = *No chord*
* `23` = Major seventh flatted fifth [CM7♭5]
* `24` = Flatted fifth [C(♭5)]
* `25` = Minor major seventh flatted fifth [CmM7♭5]
* `26` = *1+♭2+♭3* [C*]
* `27` = *1+♭2+♭5* [C*]
* `28` = *1+♭2+5* [C*]
* `29` = *1+♭2+♭7* [C*]
* `2A` = *1+2+3* [C*]

In addition to the chords listed in the manual, there are undocumented supported (pseudo-?)chords `22` and `26`–`2A`, listed above in *italics*.

Chord `22` can be obtained by itself by pressing what would be three consecutive notes but with one transposed to a different octave.
For example, a "B-`22` chord" can be obtained with C+D♭+B (i.e. B+C+D♭, but with the B transposed up an octave). This causes the chord accompaniment to go silent, as if there is no current chord.
It can also be obtained with a bass note, in which case no transposition is necessary. For example a "D♭-`22`/C chord" can be obtained with C+D♭+D+E♭, and a "C-`22`/G chord" with G+C+D♭+D.
This causes the accompaniment to play with the bass note only. In either case, the chord display becomes blank.

(The XF specification calls this no-chord "cc".)

Chords `26` through `2A` are displayed in the chord display with an asterisk, like "C*". Although they display the same, they are different chords with different accompaniments.
The key combinations are listed above; for example a C*1+♭2+5* chord is obtained with the keys C+D♭+G.

(Strictly speaking, Octave and Perfect fifth are not 'chords' and are not listed as such in the manual's table. Nevertheless, they are mentioned in the manual below the chord table. The 'Perfect fifth' is also known as a 'power chord'.)


###### Chord Bytes

For most chords, `cr ct` and `bn bt` are the same. For example, an E major chord is `33 00 33 00`, an A minor (Am) chord is `36 08 36 08`, and a G sharp minor major seventh flatted fifth (G♯mM7♭5) chord is `45 25 45 25`.

The DGX-505 also supports chords with different bass notes, which appear after a slash, e.g. "C/G" or "Am/D♭". For these chords, `bn bt` takes the value of the bass note's octave-chord (i.e. `bn 1E`). For example, C major with F bass is `31 00 34 1E`.

This also applies to the special chord types `22` and `26`–`2A`.


###### System Exclusive Chord Change

The MIDI files on the supplied CD-ROM have a different method of specifying chord changes, using System Exclusive messages instead of meta-events.

The System Exclusive messages have the format `F7 43 7E 02 cr ct bn bt 7F`, where `cr ct bn bt` is of the same format described previously.

(Both of these schemes are different
defined in Yamaha's XF Format specifications from 1999.
There, chord changes are through meta-events with data `43 7B 01 cr ct bn bt`.)


##### Style Number

`43 76 1A 04 ss ss`

where ss is the style number, minus 1.

*I'm not sure why two bytes are needed.*


#### Track Contents

The contents of the time track are as follows:

(Note that the byte representations for sysex messages are different in the actual file (see the midi spec), but are presented here as regular messages.)

* Time signature meta-event, `FF 58 04 nn dd cc bb`
  - The numerator `nn` is the time signature value as displayed by the DGX-505
  - denominator is quarter-notes (`dd` = `02`)
  - 24 MIDI Clocks per metronome click (`cc` = `18`)
  - 8 notated 32nd-notes per MIDI quarter-note beat (`dd` = `08`)
  - This can be overwritten if Track A is not recorded.

* Tempo meta-event, `FF 51 03 tttttt`
  - Tempo is given in microseconds per beat (quarter-note).
  - This can be overwritten if Track A is not recorded.

* GM System ON SysEx message, `F0 7E 7F 09 01 F7`
  - This resets all the channel settings to default (see [DGX-505 MIDI document](./DGX505Midi.md)).

* Reverb Type SysEx message, `F0 43 15 4C 02 01 00 mm ll F7`
* Chorus Type SysEx message, `F0 43 15 4C 02 01 20 mm ll F7`
  - These set the reverb and chorus types for the song. (see [DGX-505 MIDI document](./DGX505Midi.md))
  - The reverb and chorus types specified here are those specified by the most recently recorded track. This part gets overwritten if a new track is recorded with different types, even if Track A is already recorded.
  - Note that these messages have the device-number `n` = `5`, even though the DGX-505 seems to ignore the device-ID.

* Text meta-event, `FF 01 08 20 59 41 4D 41 48 41 20`
  - The text is `" YAMAHA "` (quotes not included).
  - This text seems to mark the point where 'content' begins, although there are a few more messages to go with time 0.

* Style number proprietary meta-event, `FF 7F 06 43 76 1A 04 ss ss`
* Style volume proprietary meta-event, `FF 7F 05 43 76 1A 02 vv`
* Section change proprietary meta-event, `FF 7F 05 43 76 1A 01 xx`
  - These three Style/section meta-events are present whether there actually is a recorded style or not; they just don't have any effect if there isn't.

* If Track A is recorded, the rest of Track A's messages (tempo, chord and section changes) follow afterward from here.

* The track ends, as all tracks do, with an End of Track meta-event, `FF 2F 00`


### The Song Tracks, and the weird repurposed event (?)

The song tracks contain the recorded notes and other assorted information (refer to manual for what's recorded). The way some of this is represented is a little surprising to me.


#### Channels

Each track records its messages on two channels, one for the main voice and one for the dual voice.

In decimal, human-exposed one-based notation, Track *n*'s main voice is on channel *n*, and its dual voice uses channel 10+*n*. In hexadecimal zero-based notation, this means:

| Track | Main channel | Dual Channel |
|-------|--------------|--------------|
|   1   | `0`          | `A`          |
|   2   | `1`          | `B`          |
|   3   | `2`          | `C`          |
|   4   | `3`          | `D`          |
|   5   | `4`          | `E`          |

Harmony notes are recorded as if they are main notes; the Split notes are not recorded.

Harmony volume is represented by different velocities for the Harmony notes compared to the Main notes.

Note that these channels are not the same as the channels that the song is output over the regular Song Out MIDI. Those use channels `3`–`7` and do not output Dual notes (see [DGX-505 MIDI document](./DGX505Midi.md)).


#### Octave representation

The Octave of the Dual voice is represented directly in the recorded notes, for example if the Dual Octave is set to +1 and key C3 (note 60, `3C`) is pressed, then the recorded dual note in its channel is C4 (note 72, `48`).

In contrast, the Octave of the Main voice (and consequently, Harmony notes as well) is not represented in the notes.
If Main Octave is +1 and key C3 is pressed, it is recorded as C3, even though upon playback of the User Song, the note C4 would be produced.
(This is even the case for drum kits.)

The octave offset information is instead represented with a message `An 00 xx`, recorded alongside the control change messages.
Strictly speaking, this is a Polyphonic Aftertouch message for note `00`, but it obviously isn't being used for that purpose in the DGX-505 user song internals.

##### Voice Octave 'message'

Repurposed polyphonic aftertouch on note 0: `An 00 xx`

* `n` is the channel of the Main voice
* `xx` is the octave offset around the neutral value 64/`40`:
  - `3E` = -2
  - `3F` = -1
  - `40` = ±0
  - `41` = +1
  - `42` = +2

For example, Octave offset 0 for Track 1 is `A0 00 40`,
and Octave offset -2 for Track 2 is `A1 00 3E`.


#### Track Contents

The contents of a song track are generally as follows:

* Reverb Type SysEx message, `F0 43 1n 4C 02 01 00 mm ll F7`
* Chorus Type SysEx message, `F0 43 1n 4C 02 01 20 mm ll F7`
  - For these messages, the device-number `n` appears to be the same as the Main voice channel.
  - These reverb and chorus type messages don't seem to have an effect directly, they appear to be overridden by the reverb and chorus types specified in the time track.

* Text meta-event, `FF 01 08 20 59 41 4D 41 48 41 20`
  - The text is `" YAMAHA "` (quotes not included).
  - As with the time track, this text seems to mark the point where 'content' begins, although there are a few more messages to go with time 0.

* Following from here are the initial parameters recorded for the main and dual channels: Bank/Program, Pitch bend range, reverb and chorus levels, channel volume and pan and so on. See the [DGX-505 MIDI document](./DGX505Midi.md) for an explanation of the control change messages.
  - There are two interesting messages here:
    - Expression (Control 11/`0B`), which I don't think can be set with the panel but can be affected by other things (?)
    - Effect 4 "Variation" (Control 94/`5E`), which is not an effect supported by the DGX-505, but seems to be set anyway (to zero).
  - Also included in this section is the Main Voice Octave 'message' described earlier.

* The main content, notes, additional program and control changes, etc. follow afterward.
  - Note that Dual and Harmony ON/OFF etc. are not recorded as any special message, but just as the presence or absence of Harmony and Dual notes.

* At the end, the Main and Dual channels are silenced with the 'All Sound OFF' controller (control 120/`78`),
followed by the End of Track meta-event.


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

Note that this procedure only extracts the information recorded in the User Song data.
The notes will be there, but any accompanying Style will not.
The DGX-505 does not support playing back the Style from the style number meta-events for a song transferred into, say, the flash memory.
(The chord changes seem to work though.)

If you want the song with accompaniment, you could try recording the song as it plays back over the regular MIDI output, and then manually combining it in some clever way with the extra data extracted from the dump (chords, tempo, dual notes) that isn't present over the regular MIDI output. You'd have to deal with the 16 channel limitation somehow as well.

Also note that because of the way that the DGX-505 stores the Main Octave for user songs, just taking the user-song as-is might leave the main voices in the wrong octave.
Each note will have the wrong octave (or play the wrong drum in a drum kit), so a transposition to the proper octave may be necessary.


## Registration (a.k.a. One-Touch-Settings) data format

### Overall Structure

The second-last message, no. 40, contains 816 encoded bytes that decode to 714 bytes, structured roughly as follows.


#### "PSR"

Offset: `000`, Length: `4`

The registration data is book-ended by `50 53 52 03`, the which happens to be
ASCII for "PSR" plus `03` (end-of-text control character?)


#### One-Touch-Settings

Offset: `004`, Length: `2C` × 16

The DGX-505 has 8 banks × 2 buttons = 16 settings that can be saved.
Each is represented here with 44 (hex: `2C`) bytes.
The settings are organised primarily by button, then by bank, i.e.
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

Each setting is stored in 44 bytes. If the setting is unrecorded, all of
these bytes are `00`. Otherwise, each setting has the following structure:

#### ??

Offset: `00`, Length: `1`

Recorded settings have the first byte with value `01`.
I suspect this may be the flag that records whether the setting is in use.


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

This one uses weird values for ON and OFF, probably because internally this is
actually tweaking the *Release Time* parameter which can be set with MIDI
messages for external inputs, but can only be set to `40` (64) and `6E` (110)
using the Panel Sustain feature.

* `40` = Sustain OFF
* `6E` = Sustain ON


#### ??

Offset: `2A`, Length: `2`

Two more zero bytes.
