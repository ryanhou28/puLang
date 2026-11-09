# The puLang Compiler

puLang compiles music the way a compiler compiles programs. A song starts as intent
(harmony, form, patterns), and four dialects lower it step by step until it is the
tracks, clips and notes of a DAW project. Each step is a pass you can read, change or
replace. You can then edit the result in kaiDAW and keep composing in source, because
recompiling keeps your edits.

```
song.py  or  song.mlir
   │
   ▼
intent.*   harmony, form, patterns, racks
   │  lower-intent-to-score    lay the form out in time, one slot per chord per part
   │  voice-lead               choose every chord's voicing across the whole progression
   │  realize-patterns         expand the slots into notes
   ▼
score.*    named pitches in bars, voices, a chord timeline
   │  lower-score-to-event     absolute time, articulation
   ▼
event.*    MIDI pitches and exact times
   │  swing, humanize, accent, pump
   │  lower-event-to-daw       clips and integer ticks
   ▼
daw.*      tracks, clips, notes, plugins, automation
   │  overrides                put back the edits you made in the DAW
   │  diff against the project
   ▼
one undoable transaction to kaiDAW
```

The dialects are built on [xDSL](https://xdsl.dev), so every level prints as text,
parses back exactly, and verifies. Time is an exact fraction of a quarter note until
the last lowering, so a triplet stays a triplet.

## Using it

```sh
pulang ir song.py --stage score      # print the IR at any stage
pulang trace song.py -o build/       # write the IR after every pass
pulang check song.py                 # read through the music for likely mistakes
pulang midi song.py -o song.mid      # write a MIDI file

pulang push song.py                  # make kaiDAW hold the song
pulang status song.py                # what would a push do?
pulang pull song.py                  # keep the edits made in the DAW
pulang edits song.py                 # list those edits
pulang drop song.py <location>       # forget one
pulang render song.py -o song.wav    # bounce it
pulang stems song.py -o stems/       # bounce each track alone, and measure them
pulang save song.py 'C:\songs\x.kaidaw'
pulang watch song.py                 # push on every save
```

Install with `pip install -e .`, and start kaiDAW with `tools/build-windows.sh serve` from its
repo. Add `--port` if it is not on 8899. From WSL, puLang reaches a Windows server through
`curl.exe` automatically.

A song is a Python file:

```python
from pypulang import *
from pypulang.compiler.passes.perform import Swing

with piece(tempo=132, key="C major", title="Blue") as song:
    a = song.section("a", bars=8)
    a.chart("Dm9 G13 | Cmaj9 | Em7 A7alt | Dm9 G7alt")
    a.track("bass", role=Role.BASS).pattern(walking_bass)
    a.track("keys", role=Role.HARMONY).pattern(comp).voicing("rootless", 52, 72)
    a.track("lead", role=Role.MELODY).line("a5/8 g5 f5 e5 d5/4 c5 | b4/1")

pipeline = {"event": [Swing(tracks=("keys",))]}
```

Or a text file of `intent` IR, written by hand or printed by `pulang ir`:

```mlir
builtin.module {
  intent.piece "Blue" tempo 1.320000e+02 : f64 key <"C major"> meter <4/4> {
    intent.section "a" bars 2 : i64 {
      %0 = intent.harmony [#mus.chord<"ii(9)">, #mus.chord<"V(13)">, #mus.chord<"I(maj7,9)">] for [#mus.r<1/2>, #mus.r<1/2>, #mus.r<1>] in "bars" : !intent.harmony
      intent.track "bass" role "bass" instrument "piano" octave 0 : i64 velocity 100 : i64 muted 0 : i64 {
        intent.pattern "walking_bass" over %0 with {} : !intent.harmony
      }
    }
  }
}
```

Harmony is an SSA value that tracks point at. A pass that rewrites one `intent.harmony`
changes what every track in that section plays, and nothing else has to be told.

## Writing music

| Tool | What it does |
|---|---|
| `section.chart("Dm9 G13 \| Cmaj9 \| % \| A7alt")` | Harmony as a lead sheet. Loops to fill the section. |
| `track.line("a4/8 c5 e5/4. r/8 \| g5/2~ g5/8 f5")` | A melody. Values carry over; `>` accent, `?` ghost, `'` staccato, `~` tie. `\|` checks the bar adds up. |
| `grid(cell="x..o..x.", pitch=36)` | Drums on a step grid, in any meter. |
| `hits(cell="x-.x-.x.")` | The voicing on a rhythm: stabs, pads, written-out comping. |
| `riff(cell=..., degrees="1 5 b7 1'")` | A line in chord degrees, so it follows the changes. |
| `walking_bass`, `comp`, `solo_line` | Generators that see the chord, the next chord, and the bar. |
| `track.voicing("rootless", E3, C5)` | close, shell, rootless, drop2, quartal, upper_structure, wide. |
| `song.rack("pad", surge("synth", warm_pad()), sends={"verb": 0.4})` | How a track sounds. |
| `section.automate("pad", "synth.A Filter 1 Cutoff", [(0, a), (8, b)])` | A parameter moving, in bars. |
| `verse.transform("chorus", reharmonize="tritone_sub", transpose=2)` | A new section from an old one. |

`1/4` means a quarter note everywhere in the DSL. The IR counts in quarter-note beats, and
the DSL converts. Chord durations in `harmony()` are in bars.

Passes run where you ask, through a song's `pipeline`:

| Stage | Passes |
|---|---|
| `intent` | `Reharmonize` (tritone_sub, jazzify, modal_interchange, secondary_dominants), `Transpose` |
| `event` | `Swing`, `Humanize`, `Accent`, `Pump`, `Bend` |

`Pump` ducks a track's fader on every hit of another. It makes the sidechain sound from a
volume curve, so it needs no routing.

`Bend` writes pitch bends on a track's long notes: a `scoop` up into the note from below, or a
`fall` off its end. Bends go in the clip's pitch-bend lane, which every instrument hears and a
person can redraw in the DAW, and each clip's lane is returned to rest before it ends. Run it
after `Humanize`, so the bends follow the notes where they landed.

A section's time signature and name reach kaiDAW too: its meter map shows 7/8 where the source
says 7/8, and every section occurrence is a marker.

## Voice leading

A voicing strategy returns every arrangement of a chord that fits the register. It does not
choose. `voice-lead` then takes each run of chords as one problem and finds the shortest
path through the candidates, weighting the top voice most because that is what a listener
follows. `Dm9 G13 Cmaj9` comes out as C-E-F-A, B-E-F-A, B-D-E-G, where one voice moves at a
time. A test checks the result against a brute-force search.

Slots are still IR at this point, so `pulang trace` shows the voicings before any note exists.

## Editing in the DAW

Every note carries a location naming its musical position:

```
verse#2 / keys / bar 3, beat 1/2, voice 1
```

That location is its identity across recompiles. A position survives what a chord index
would not: substituting a chord leaves every later note where it was. Repeats are call sites
of one source, which is what MLIR's `CallSiteLoc` is for, so a verse played twice is two sets
of notes with one origin.

Two files sit beside a song, in `<song>.pulang/`:

- **`lock.json`** is the source map: what was last pushed, and which kaiDAW id each location
  became. It belongs to one project on one machine and is not committed.
- **`overrides.json`** holds your edits and is part of the song. Commit it. The compiler
  applies it on every compile, so notes are a pure function of source plus overrides, and a
  fresh build on another machine gets your edits back.

The rule that decides what a push may touch:

| Owned by the source | Owned by the DAW |
|---|---|
| Generated notes, clips, tempo | Plugin state, the mix, automation you drew |
| Plugins and levels the source declares, when the source value changes | Any clip or track made by hand |

So a fader you moved stays moved until the source changes that fader, and a plugin you
added stays in the chain.

Every push captures your edits first:

| You did this in the DAW | What happens |
|---|---|
| Moved or changed a note | Kept, and recorded as an override |
| Deleted a note | Stays deleted. This is recorded as an edit, because kaiDAW creates a note when sent an id it does not know, so otherwise a harmony change would bring it back. |
| Drew a note | Kept, attached to its clip |
| Moved or deleted a clip | Stays that way |

A push never silently discards a hand edit, and it tells you about the two cases that need a
decision:

- **Stale:** you edited a note and the source has since changed under it. Your edit wins, and
  `pulang push` says what the source would now give. `pulang drop` takes the source's side.
- **Orphaned:** the source no longer makes that note at all. Your edited note stays, as a note
  of its own.

A push is one transaction, so one undo in the DAW takes it back. Pushing the first time also
sends a transaction of whole patches if any device names one, then one for plugin modes if any
has a mode to set, then one for parameters, because those need ids that exist only after the
tracks do and Surge applies patches and modes on its next audio block.

Controller lanes follow the same rule as parameters: one is sent when its source changes, so a
bend redrawn in the DAW stays redrawn until the source changes that lane.

On Slow Orbit, moving a note, deleting one, changing a fader and adding a delay, then changing
one chord of the head in the source, updated 85 notes and left 3,495 alone. All four hand
edits survived and the deleted note was reported as stale.

## Audio and samples

A section can play an audio file on a track, and a rack can be a sampler with files on its
keys:

```python
from pypulang import *
from pypulang.sounds import sampler

with piece(tempo=140, key="F minor", title="Samples") as song:
    song.rack("drums", sampler("kit", {36: "samples/kick.wav", 38: "samples/snare.wav"}))
    drop = song.section("drop", bars=4)
    drop.harmony(i, VI)
    drop.track("drums", role=Role.RHYTHM).pattern(grid(cell="x...o...x.x.o...", pitch=36))
    drop.audio("vox", "samples/chop.wav", at=1, length=1 / 4, gain_db=-3)
```

`audio` places a file `at` bars from the section start, for `length` bars or to the end of
the file, from `offset` seconds into it. It lowers like automation does, once per occurrence:
`intent.audio` in the section, `event.audio` at an absolute beat, and `daw.audio` with a key
such as `drop#2/vox/audio0`, so each occurrence is its own clip in the DAW. A sampler's sounds
ride on its `daw.plugin`. A bare path plays on its key alone and to its end, which is what a
drum pad is; a dict sets `root`, `low`, `high`, `gain`, `pan` or `one_shot`.

Push imports each file into kaiDAW's media pool once, and again only if it changes on disk
or the server has lost it. Audio clips follow the rule notes and parameters follow: one moved
or deleted in the DAW stays that way, and one is changed only when its source changes.
Paths are relative to the song file. kaiDAW reads WAV, AIFF and FLAC.

## Sound

`pypulang.sounds` holds a measured vocabulary for Surge XT: names and units for values a host
only sees as numbers from 0 to 1. Patches are dictionaries, so you can merge and tweak them.

A device can also start from one of Surge's own factory patches, loaded whole:

```python
from pypulang import *
from pypulang.compiler.passes.perform import Bend
from pypulang.sounds import cutoff, surge

with piece(tempo=96, key="F major", title="Patches") as song:
    song.rack("keys", surge("synth", patch="Keys/Soft Suitcase"))
    song.rack("lead", surge("synth", {"A Filter 1 Cutoff": cutoff(2400)}, patch="Leads/Acidofil"))
    a = song.section("a", bars=2)
    a.chart("Fmaj7 | Bb9")
    a.track("keys", role=Role.HARMONY).pattern(comp).voicing("rootless", 52, 72)
    a.track("lead", role=Role.MELODY).line("c6/2 a5 | f5/1")

pipeline = {"event": [Bend(track="lead", kind="scoop", semitones=1, min_length="1/2")]}
```

Parameters given with a patch are written on top of it. The patch name stays in the IR
(`daw.plugin "synth" is ... patch "Keys/Soft Suitcase"`) and becomes plugin state only when it
is sent: `pypulang.sounds.surge_patches` reads the `.fxp` from Surge's install and wraps it the
way a JUCE host stores a VST3's state, and kaiDAW's `RestorePluginState` loads it. A patch is
sent when the source names a different one, so a patch changed inside Surge's editor stays
changed. Set `SURGE_PATCHES` if the factory folder is somewhere unusual. Slow Orbit's Rhodes
and pad are factory patches; the parameter-built `electric_piano()` and `warm_pad()` are still
there to compare. One limit, kaiDAW's: after a patch loads, its projection keeps showing the
previous patch's parameter values until the project is reopened, because Surge does not tell
the host. Writes still reach the plugin.

Everything in both songs is synthesised, including the drums. The kick's pitch drop comes from
a resonant filter ringing as its envelope falls, measured sweeping 356 Hz to 52 Hz in 36 ms.
Host parameters cannot reach Surge's modulation matrix, so an oscillator's pitch cannot be
swept directly.

Two things about Surge are worth knowing if you write patches:

- Setting an oscillator, filter or FX **type** resets the parameters that belong to it, on the
  next audio block. Push handles this: it writes types first, runs a moment of audio, then
  writes the rest. A parameter named `... Type` is treated this way.
- Surge renames some parameters to suit the active oscillator, on the first instance in a
  process only ("Sub Mix" becomes "M2 Ratio"). Patches use the generic names, and push learns
  them from a new instance, where they are always generic.
- Surge's `Polyphony Limit` defaults to 16 voices, which a wide chord through unison saws
  exceeds. The chord patches raise it.

`pypulang.analysis` measures renders: loudness, spectral balance, pitch. `pulang stems` uses it
to print a table of every track. Measurements catch silence, clipping and a buried part. They
cannot tell you a mix sounds good.

## Status

What exists and is tested:

| | |
|---|---|
| Dialects | `mus`, `intent`, `score`, `event`, `daw`, all round-tripping through text |
| Lowerings | All four, held note for note to the original realizer on the examples and on 150 generated pieces |
| Voicing | Seven strategies and exact voice leading |
| Harmony | Chart symbols, altered tensions, slash bass, reharmonization, transposition |
| Performance | Swing, humanize, accent, pump, bend |
| kaiDAW | Push, pull, status, overrides, render, stems, save and reopen; time signatures, section markers, the master fader, pitch bend and CC lanes, whole Surge patches |
| Audio | Files on tracks per section, and samplers with files on keys, imported into kaiDAW's pool |
| Review | Melody against harmony, ranges, parallels |

Not built, and described elsewhere in these docs:

| | |
|---|---|
| `.pu` standalone syntax | Python and text IR cover both ways of writing a song for now |
| Lifting | Inferring IR from notes. Overrides keep DAW edits without it. |
| MusicXML | No score output yet |
| Analytical dialects | Schenkerian, set theory, and so on. Dialects are ordinary xDSL, so nothing blocks them. |
| `density`, `tempo_scale` on `transform` | The language spec names them; neither has a defined meaning yet |

See [kaidaw-findings.md](kaidaw-findings.md) for what the songs need from kaiDAW.
