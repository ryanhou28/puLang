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

pulang variations song.py            # each site's alternatives, and which is picked
pulang propose song.py "chorus hook" hook-b 'motif/hook:notes=3/4 2/8 1 ...'
pulang pick song.py "chorus hook" hook-b
pulang audition song.py "chorus hook" -o takes/
pulang agent describe '{"song": "song.py"}'   # one agent tool, JSON in and out
pulang mcp                           # the agent tools as an MCP server on stdio
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
| `song.motif("hook", "5/8 6 1'/4 7/8 5/4.")` | A short idea in scale degrees, for melodies to develop. See [Motifs](#motifs). |
| `track.melody("hook; hook +1; hook inv end 1")` | A melody as motifs: stated, sequenced, inverted, answered, fitted to the chords. |
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
| `event` | `Swing`, `Humanize`, `Accent`, `Pump`, `Bend`, `LayBack`, `Phrasing`, `Legato`, `Dynamics` |

`Pump` ducks a track's fader on every hit of another. It makes the sidechain sound from a
volume curve, so it needs no routing.

`Bend` writes pitch bends on a track's long notes: a `scoop` up into the note from below, or a
`fall` off its end. Bends go in the clip's pitch-bend lane, which every instrument hears and a
person can redraw in the DAW, and each clip's lane is returned to rest before it ends. Run it
after `Humanize`, so the bends follow the notes where they landed.

The feel of a band is mostly where each player sits and how they shape a line. `LayBack`
plays a track a constant number of ticks behind the beat (or ahead, negative): a bass on the
beat and a lead 20 ticks behind sounds unhurried. `Phrasing` treats each run of notes between
rests as a phrase and shapes its velocity, rising to its highest note and letting go after
it, with the last note softest. `Legato` holds each note until the next begins, a few ticks
into it so a synth with glide slides, and leaves real rests alone. `Dynamics` gives each
section a mark, `pp` to `ff`, or a swell such as `p<f` that builds across the section;
`mf` leaves velocities as written.

A section's time signature and name reach kaiDAW too: its meter map shows 7/8 where the source
says 7/8, and every section occurrence is a marker.

## Motifs

A melody written as notes has nothing to come back to. One written as motifs does: name a
short idea once, in scale degrees, and a phrase states it and develops it.

```python
from pypulang import *
from pypulang.pitches import A5, C5, E3, E4

with piece(tempo=96, key="D minor", title="motifs") as song:
    song.motif("hook", "5/8 6 1'/4 7/8 5/4. r/8")
    song.motif("sigh", "3/4 2/2")
    verse = song.section("verse", bars=8)
    verse.chart("Dm9 | Gm9 | C7 | Fmaj7 | Bbmaj7 | Em7b5 | A7 | Dm9")
    verse.track("lead", role=Role.MELODY).melody(
        "hook; hook +1; hook inv end 1; rest 2; sigh x2", low=E4, high=A5
    )
    verse.track("keys", role=Role.HARMONY).pattern(comp).voicing("rootless", E3, C5)
    song.form([verse])
```

A motif token is a degree 1-7, with `b` or `#` before it to alter it and `'` or `,` after it
for an octave up or down, then a note value as in `line`. `!` is staccato; `>`, `?` and `~`
are as in `line`. A phrase is placements separated by `;`, played one after another, and a
placement is a motif and its developments, applied left to right:

| Development | What it does |
|---|---|
| `+2`, `-1` | Sequence: every note moved by scale steps |
| `^`, `v` | An octave up or down |
| `inv` | Inversion around the first note |
| `rev` | Retrograde, rhythm included |
| `x2`, `x1/2` | Augmentation and diminution |
| `first 3`, `last 2` | A fragment |
| `end 1` | End on a degree: the answer to a question |
| `vary 3` | Passing and neighbour notes; the same number gives the same ornaments |
| `early 8`, `late 16` | Anticipate or delay by a note value |
| `rest 2` | A placement of silence |

Degrees are read in the section's key, so a melody follows a key change or a transposition.
The first placement sits in the octave whose tonic is nearest the middle of the range, and
each later one in the octave nearest to where the line already is. The range is a strong
preference: a sequence climbing a step past the top stays put, and one climbing further
drops an octave. With `fit` (the default), a note on a strong beat or held for a beat that is
a semitone above a tone of the chord under it moves to the nearest note that belongs, so a
fourth held over a major chord resolves to the third; 9ths, 11ths over minor chords, and 13ths
are kept.

Motifs and phrases are edits at the intent level too: `motif/hook` with field `notes` changes
every place the motif is used, and a track's `melody` field changes its phrase. The companion
page shows both for a melody track.

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

## Editing above the notes

A note moved in the DAW is a note edit. Some edits mean more than their notes: the chord a
section plays, the voicing of one chord, a part's octave. Those are kept at the level they
were made at, as edits of the IR, and applied by a pass when the song compiles:

| Level | Target | Fields | Reaches |
|---|---|---|---|
| intent | `verse/harmony` | `chart` | the whole progression, as a chord chart; a short one loops |
| intent | `verse/harmony@3+0` (the chord starting at bar 3, beat 0) | `chord` | every occurrence of the section |
| intent | `verse/keys` | `voicing`, `octave`, `velocity`, `muted`, `pattern`, `melody` | every occurrence |
| intent | `motif/hook` | `notes` | every place the motif is used |
| score | `verse#2/harmony@3+0` | `chord` | the second verse only; voiced in context |
| score | `verse#2/keys/c4` | `pitches` | the exact notes of one chord in one part |

They live in `overrides.json` beside the note edits, so a song is still its source plus its
overrides, and `pulang ir` shows them applied. A chord changed at the score level is voiced
afresh by voice leading and every part follows it, so the bass plays the new root. Like a
note edit, an edit made when the source said one thing and applied after it changed is
reported as stale, and one whose place no longer exists as orphaned. `pulang edits` lists
them as `level:target:field`, and `pulang drop` takes that name.

`pulang serve song.py` serves a page that kaiDAW shows in its source tab. Select a clip, or
notes in the piano roll, and it shows what produced them at every level, from the note in
kaiDAW through the event and score notes to the chord slot, the chord and the section's
track settings, each with the edits that level takes. An edit is recompiled and pushed at
once.

The page can also read hand edits made in kaiDAW. Each reading is a guess at the higher edit
they mean: a new voicing of a chord, a different chord, the part an octave up, the part
muted. Every guess is checked by lowering the song with it, and is shown with how many of
the hand edits it reproduces exactly and how many notes nobody touched it would also change.
A chord the edited notes spell is offered together with the voicing as played, because a new
chord on its own would be voiced afresh: the pair keeps the notes and tells the other parts
what the harmony now is. Keeping a reading drops the note edits it explains.

## Variations

A variation is an alternative for one place in a song: a named bundle of the edits above,
at a site such as "chorus hook" or "verse harmony". Anyone can propose one, a person or an
agent, and the source is always the first alternative at every site. Proposing keeps the
bundle in the song's overrides without playing it; picking one makes every compile apply
its edits. Chosen variations apply before hand edits, so a hand edit still has the last
word. Alternatives at one site replace each other, and picking `source` goes back to the
song as written.

```sh
pulang propose song.py "chorus hook" hook-high "motif/hook:notes=1'/8 7 6 5/4. 3/8" \
    --description "from the octave down"
pulang audition song.py "chorus hook" -o takes/   # source.wav, hook-high.wav, ...
pulang pick song.py "chorus hook" hook-high
```

A bundle is checked by compiling the song with it before it is kept, and is refused if the
compiler rejects it, if it aims at a place the song does not have, or if it changes no
notes. It is described by what it does: which section occurrences and parts change, and how
many notes. `audition` renders the source and every alternative at a site through kaiDAW
over the same bars, the first occurrence any of them touches with a bar before it, so they
can be compared directly, and pushes the song back as picked when it is done. The companion
page in kaiDAW's source tab lists the sites and picks with one click.

## Agent tools

An agent cannot hear a song, but it can read one at every level, change it at the level a
change belongs to, propose alternatives for a person to hear and pick, review the result,
and render a window to measure. `pypulang.agent` does each of those to a song file and
returns plain data:

| Tool | What it does |
|---|---|
| `describe` | The song in one read: form with bars and times, each section's chart, every track's part, motifs, edits, variations |
| `ir` | The IR at one stage, optionally one section |
| `review` | The compiler's read-through, and each melody's range and density per section |
| `edit`, `drop` | Change one thing above the notes and keep it, or forget it |
| `propose`, `pick`, `drop_variation`, `variations` | Variations, as above |
| `render` | Push to kaiDAW and bounce a section occurrence, some bars, or the song, with its levels |
| `audition` | Render every alternative at a site |

Every change is checked by compiling before it is kept and comes back with the notes it
changed and any warning it brought. The same tools are `pulang agent <tool> '<json>'` for
scripts and `pulang mcp`, a Model Context Protocol server on stdio, for an agent such as
Claude Code: `claude mcp add pulang -- pulang mcp`.
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

The example songs play sampled drums: `fusion_rack(song, kit="samples/jazz")` and
`future_bass_rack(song, kit="samples/future")` put one sampler per drum track, on the keys
the Surge stand-ins used, with gains measured so each drum sits where its stand-in did.
The kits are not in the repository. `python scripts/get_drum_samples.py` builds them into
`examples/songs/samples/` from their sources in about half a minute: a jazz kit from
[Virtuosity Drums](https://versilian-studios.com/virtuosity-drums/) (CC0), each hit mixed
from its close, overhead and room mics, read straight out of the 1.2 GB archive with range
requests; and a future-bass kit of CC0 Kickmess kicks and TR-909 hits by F9 Audio, which are
free to use but not to redistribute. Without a `kit`, the racks use the Surge drums.

Acoustic instruments are sampled the same way. `sampled("keys", "piano")` is a sampler with a
zone per sample, each key playing the nearest one: `piano` (a Steinway B), `upright_bass`
(pizzicato), `vibes`, `muted_trumpet`, `trumpet`, `trumpet_stab`, `trombone`, `trombone_stab`,
`tenor_sax`, and `strings` (cellos, violas and violins across the range), from
`pypulang.sounds.instruments`. `python scripts/get_instrument_samples.py` builds them into
`examples/songs/samples/instruments/` from two CC0 libraries, the
[Versilian Community Sample Library](https://github.com/sgossner/VCSL) and
[VSCO 2 Community Edition](https://github.com/sgossner/VSCO-2-CE), downloading only the
seconds each sample keeps. kaiDAW's sampler plays one sample per key and follows velocity
with gain, so each instrument is one dynamic layer of its library, and a note held longer
than its sample (six seconds for sustained sounds) runs out. The tables name the note each
sample really sounds, checked with a pitch detector, since most of these libraries call
middle C "C3".

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
| Melody | Motifs in scale degrees, developed in phrases and fitted to the chords |
| Performance | Swing, humanize, accent, pump, bend, lay-back, phrasing, legato, dynamics marks |
| kaiDAW | Push, pull, status, overrides, render, stems, save and reopen; time signatures, section markers, the master fader, pitch bend and CC lanes, whole Surge patches |
| Editing above the notes | Intent and score edits kept at their level; `pulang serve` traces a DAW note up every level; hand edits read back as chords, voicings, octaves, velocity and mutes, each checked by lowering |
| Variations | Alternatives as bundles of edits at a site, proposed, auditioned and picked; the source always one of them |
| Agent tools | Describe, IR, review, edit, propose, pick, render, audition, over a JSON CLI and an MCP server |
| Audio | Files on tracks per section, and samplers with files on keys, imported into kaiDAW's pool |
| Review | Melody against harmony, ranges, parallels |

Not built, and described elsewhere in these docs:

| | |
|---|---|
| `.pu` standalone syntax | Python and text IR cover both ways of writing a song for now |
| Lifting a whole song | Hand edits are read up one step, to chords, voicings and track settings. Inferring a section's pattern or form from bare notes is not attempted. |
| MusicXML | No score output yet |
| Analytical dialects | Schenkerian, set theory, and so on. Dialects are ordinary xDSL, so nothing blocks them. |
| `density`, `tempo_scale` on `transform` | The language spec names them; neither has a defined meaning yet |

See [kaidaw-findings.md](kaidaw-findings.md) for what the songs need from kaiDAW.
