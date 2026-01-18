# pyPuLang Language Specification

*Draft v0.1 — Subject to change*

This document specifies **pyPuLang**, the Python-embedded syntax for puLang. A standalone puLang syntax is co-designed but documented separately.

---

## Overview

pyPuLang is a Python-embedded DSL for music composition. It uses context managers, method chaining, and declarative constructs to express musical intent.

### API Style

pyPuLang supports multiple coding styles:

```python
# Method chaining (fluent)
verse.track("bass").pattern(root_eighths).octave(-2).velocity(100)

# Separate statements
bass = verse.track("bass")
bass.pattern(root_eighths)
bass.octave(-2)
bass.velocity(100)

# All-in-one with kwargs
verse.track("bass", pattern=root_eighths, octave=-2, velocity=100)
```

All styles are equivalent. Use whichever feels natural.

---

## Core Constructs

### 1. `piece`

The top-level container. Everything exists within a piece.

```python
from pypulang import *

with piece(tempo=120, key="D major", time_sig="4/4") as p:
    # sections, tracks, etc.
    ...

p.save_midi("output.mid")
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tempo` | `int \| float` | 120 | BPM |
| `key` | `str \| Key` | "C major" | Key signature |
| `time_sig` | `str \| TimeSignature` | "4/4" | Time signature |
| `title` | `str` | None | Optional title |

#### Methods

| Method | Description |
|--------|-------------|
| `.section(name, bars)` | Create a section |
| `.save_midi(path)` | Save to MIDI file |
| `.save(path)` | Save to file (auto-detect format) |
| `.to_midi()` | Return mido.MidiFile object |
| `.play()` | Play via system audio (Phase 2) |
| `.to_ir()` | Return Intent IR |

---

### 2. `section`

A formal unit of the piece (verse, chorus, bridge, etc.).

```python
verse = p.section("verse", bars=8)
chorus = p.section("chorus", bars=8)

# Length can also be specified in beats
bridge = p.section("bridge", beats=12)

# Or inferred from harmony (if bars/beats not specified)
outro = p.section("outro")
outro.harmony((I, 2), (V, 2))  # Infers 4 bars
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Section identifier |
| `bars` | `int` | optional | Length in bars (inferred if not specified) |
| `beats` | `int` | optional | Length in beats (alternative to bars) |
| `key` | `str \| Key` | inherited | Override key for this section |
| `time_sig` | `str` | inherited | Override time signature |

**Note:** If `bars` is specified and content exceeds it, an error is raised. If not specified, length is inferred from harmony/tracks.

#### Methods

| Method | Description |
|--------|-------------|
| `.harmony(...)` | Set chord progression (alias: `.progression(...)`) |
| `.track(name)` | Create or access a track |
| `.transform(...)` | Create transformed copy |
| `.transpose(...)` | Create transposed copy |
| `.repeat(n)` | Repeat section n times |

---

### 3. `harmony` / `progression`

Declares the chord progression for a section using Roman numeral notation.

**Note:** `harmony()` and `progression()` are aliases. Use whichever term feels natural.

```python
verse.harmony(I, IV, vi, V)
# Equivalent:
verse.progression(I, IV, vi, V)

# With durations (in bars)
verse.harmony(
    (I, 2),
    (IV, 2),
    (vi, 2),
    (V, 2)
)

# With modifiers
verse.harmony(I, IV, vi.dim(), V7)
```

#### Roman Numerals

| Symbol | Meaning |
|--------|---------|
| `I, II, III, IV, V, VI, VII` | Major chords |
| `i, ii, iii, iv, v, vi, vii` | Minor chords |
| `V7, IV7, ...` | Seventh chords |
| `.dim()` | Diminished |
| `.aug()` | Augmented |
| `.sus2()`, `.sus4()` | Suspended |
| `.add9()`, `.add11()` | Extensions |
| `.inv(n)` | Inversion (0, 1, 2) |
| `V/V`, `V/vi` | Secondary dominants |

#### Duration Syntax

```python
# Equal duration (bars / chord count)
verse.harmony(I, IV, vi, V)  # Each chord = 2 bars in 8-bar section

# Explicit duration in bars (default unit)
verse.harmony((I, 2), (IV, 1), (vi, 1), (V, 4))

# Explicit unit specification
verse.harmony((I, bars(2)), (IV, bars(1)), ...)
verse.harmony((I, beats(8)), (IV, beats(4)), ...)

# Chained rhythm specification
verse.harmony(I, IV, vi, V).rhythm(2, 2, 2, 2)           # bars (default)
verse.harmony(I, IV, vi, V).rhythm(bars(2, 2, 2, 2))     # explicit bars
verse.harmony(I, IV, vi, V).rhythm(beats(8, 8, 8, 8))    # explicit beats
```

---

### 4. `track`

A named voice/instrument within a section. Tracks are auto-created on first access.

```python
bass = verse.track("bass")
keys = verse.track("keys")
melody = verse.track("melody")
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Track identifier |
| `role` | `Role` | `None` | Musical role (explicit, warned if not specified) |
| `instrument` | `str \| int` | "piano" | MIDI instrument |
| `channel` | `int` | auto | MIDI channel |

#### Roles

Roles are explicit and decoupled from instrument:

```python
from pypulang import Role

# Explicit role assignment
verse.track("piano_left", instrument="piano", role=Role.BASS)
verse.track("piano_right", instrument="piano", role=Role.HARMONY)

# No default role — warning emitted if not specified
verse.track("strings")  # role = None, warning emitted
```

| Role | Description | Default Octave |
|------|-------------|----------------|
| `Role.MELODY` | Primary melodic voice | 5 (warning emitted) |
| `Role.BASS` | Harmonic foundation | 2 (warning emitted) |
| `Role.HARMONY` | Chordal accompaniment | 4 |
| `Role.RHYTHM` | Rhythmic/percussive elements | N/A (uses drum sounds) |
| `None` | No role specified | No inference (warning emitted) |

**Note:** If a role is not specified, a warning is always emitted. When octave is inferred from role, a separate warning is emitted. Explicit `.octave()` silences the octave inference warning.

**Rhythm Role:** Tracks with `Role.RHYTHM` are automatically assigned MIDI channel 10 (GM drum channel). They ignore harmony context—patterns don't receive chord information.

#### Methods

| Method | Description |
|--------|-------------|
| `.pattern(p, ...)` | Apply a pattern generator |
| `.notes([...])` | Literal notes (escape hatch) |
| `.octave(n)` | Transpose by octaves |
| `.velocity(v)` | Set velocity (0-127, 0.0-1.0, or dynamics like `mf`) |
| `.dynamics(d)` | Set dynamics (alias for velocity with musical terms) |
| `.mute()` / `.solo()` | Mute/solo for playback |

---

### 5. `pattern`

A generator that produces notes from harmony context. Patterns are callable singletons with builder methods.

#### Multiple Syntax Styles

```python
# All of these are equivalent:
track.pattern(arp)                              # Defaults
track.pattern(arp("up"))                        # Positional
track.pattern(arp(direction="up"))              # Keyword
track.pattern(arp, direction="up")              # Keyword on track.pattern
track.pattern(arp.up())                         # Builder method
track.pattern(arp("up", rate=1/16))             # Mixed
track.pattern(arp.up().rate(1/16).octaves(2))   # Builder chain
```

#### Built-in Patterns

| Pattern | Description |
|---------|-------------|
| `root_eighths` | Root note in eighth notes |
| `root_quarters` | Root note in quarter notes |
| `root_fifths` | Root + fifth alternating |
| `walking_bass` | Jazz-style walking bass |
| `block_chords` | Block chord hits |
| `arp` | Arpeggiate chord (configurable direction) |
| `alberti` | Alberti bass pattern |
| `ostinato(pattern)` | Repeating rhythmic pattern |

#### Pattern Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `rate` | `Fraction` | Note rate (1/4 = quarter, 1/16 = sixteenth) |
| `direction` | `str` | For arp: "up", "down", "updown", "random" |
| `octaves` | `int` | Octave span for arpeggios |
| `swing` | `float` | Swing amount (0.0 = straight, 0.67 = triplet) |
| `velocity_curve` | `str` | "flat", "accent_one", "crescendo", etc. |

---

### 6. Drums and Percussion

Drums use the same track and pattern infrastructure as melodic instruments, with drum-specific constants and patterns.

#### Drum Sound Constants

Import drum sounds from the `drums` module:

```python
from pypulang.drums import *

# Individual drum sounds
KICK, KICK2           # Bass drums (36, 35)
SNARE, SNARE2         # Snare drums (38, 40)
RIMSHOT, CLAP         # Rimshot, handclap (37, 39)
HIHAT_CLOSED          # Closed hi-hat (42)
HIHAT_OPEN            # Open hi-hat (46)
HIHAT_PEDAL           # Pedal hi-hat (44)
TOM_LOW, TOM_MID, TOM_HIGH  # Toms (45, 47, 50)
CRASH, CRASH2         # Crash cymbals (49, 57)
RIDE, RIDE_BELL       # Ride cymbal (51, 53)
TAMBOURINE, COWBELL, SHAKER  # Percussion (54, 56, 70)
```

#### Drum Patterns

```python
# High-level patterns
verse.track("drums", role=Role.RHYTHM).pattern(rock_beat)
verse.track("drums").pattern(four_on_floor)
verse.track("drums").pattern(shuffle(swing=0.67))

# Pattern parameters
verse.track("drums").pattern(rock_beat(hihat="open", fills=True))
```

| Pattern | Description |
|---------|-------------|
| `rock_beat` | Kick on 1/3, snare on 2/4, hihats on 8ths |
| `four_on_floor` | Kick on every beat (dance/electronic) |
| `backbeat` | Snare on 2/4 only |
| `eighth_hats` | Hi-hat eighth notes only |
| `shuffle` | Swung feel with kick/snare |

#### Literal Drum Notes

Use the escape hatch with drum constants:

```python
from pypulang.drums import *

verse.track("drums", role=Role.RHYTHM).notes([
    (KICK, 1/4), (HIHAT_CLOSED, 1/8), (HIHAT_CLOSED, 1/8),
    (SNARE, 1/4), (HIHAT_CLOSED, 1/8), (HIHAT_CLOSED, 1/8),
])
```

#### Grid Notation

For complex drum patterns, use grid notation with the `drums()` context:

```python
with verse.drums(grid=1/16) as d:
    d.kick("x...x...x...x...")      # x = hit, . = rest
    d.snare("....x.......x...")
    d.hihat("x.x.x.x.x.x.x.x.")
    d.hihat_open("..............x.")  # Open hat on beat 4 &
```

Grid characters:
- `x` — normal hit
- `.` — rest
- `o` — accent (higher velocity)
- `-` — ghost note (lower velocity)

The grid length determines one bar. Grid resolution is set by the `grid` parameter (default: 1/16).

---

### 7. `notes` (Escape Hatch)

When you need literal notes, use the escape hatch.

```python
# Pitch constants
from pulang.pitches import *

melody.notes([
    (C4, 1/4),      # C4 quarter note
    (D4, 1/4),
    (E4, 1/2),      # E4 half note
    rest(1/4),      # Quarter rest
    (G4, 1/4),
])

# Positioned notes
melody.notes([D4, F4, A4], at=beat(3))

# Chord
melody.notes(chord(C4, E4, G4), duration=1)
```

#### Pitch Notation

Pitches are `Pitch` objects (subclass of `int`) that support arithmetic:

```python
# Constants
C4, D4, E4, ...  # C4 = middle C = MIDI 60

# Sharps and flats (all enharmonic spellings available)
Cs4              # C sharp 4 (= 61)
Db4              # D flat 4 (= 61, same as Cs4)
C_sharp_4        # Long form alias
D_flat_4         # Long form alias

# Arithmetic works
C4 + 2           # D4 (MIDI 62)
C4 + 12          # C5 (octave up)
G4 - C4          # 7 (interval in semitones)

# From MIDI number
midi(60)         # Same as C4
Pitch(60)        # Same as C4
```

#### Note Syntax

```python
(pitch, duration)           # Tuple
note(C4, 1/4)              # Explicit
note(C4, 1/4, velocity=80) # With velocity
rest(1/4)                  # Rest
```

---

### 8. `transform` and `transpose`

Create modified copies of a section.

#### Basic Transform

```python
chorus = verse.transform(
    reharmonize="modal_interchange",
    density=1.3,
    register=+1
)
```

#### Transpose

Transpose has two modes: key transposition (default) and degree transposition.

```python
# Transpose key (default): same roman numerals, new key center
# Verse in C: I, IV, vi, V = C, F, Am, G
# Transposed up 5 semitones to F: I, IV, vi, V = F, Bb, Dm, C
chorus = verse.transpose(5)           # Key up 5 semitones
chorus = verse.transpose(key=5)       # Explicit key transpose
chorus = verse.transpose(-3)          # Key down 3 semitones

# Transpose degrees: same key, shift chord degrees
# Verse in C: I, IV, vi, V
# Transposed up 1 degree: ii, V, vii°, I = Dm, G, Bdim, C
bridge = verse.transpose(degrees=1)

# Both (rare)
outro = verse.transpose(key=5, degrees=1)
```

#### Transform Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `reharmonize` | `str` | Reharmonization strategy |
| `density` | `float` | Texture multiplier |
| `register` | `int` | Octave shift |
| `tempo_scale` | `float` | Tempo multiplier |
| `include_content` | `bool` | If False, only inherit structure (default: True) |

#### Transform Inheritance

By default, transforms are "full" — harmony and tracks are transformed:

```python
# Full transform (default)
chorus = verse.transform(register=+1)
# chorus has: same harmony, same tracks (shifted up one octave)

# Structure-only (no content inheritance)
bridge = verse.transform(register=+1, include_content=False)
# bridge has: same bars/time_sig, empty harmony and tracks
```

#### Transform Strategies

**Reharmonization:**
- `"modal_interchange"` — Borrow chords from parallel mode
- `"tritone_sub"` — Tritone substitution on dominants
- `"secondary_dominant"` — Add secondary dominants
- `"diatonic_sub"` — Substitute with diatonic alternatives

**See `architecture.md` for full transform documentation.**

---

## Compound Constructs

### Form / Structure

```python
with piece(tempo=120, key="C") as p:
    intro = p.section("intro", bars=4)
    verse = p.section("verse", bars=8)
    chorus = p.section("chorus", bars=8)

    # Define form
    p.form([intro, verse, chorus, verse, chorus, chorus])
```

### Repetition

```python
verse.repeat(2)  # Play verse twice

# With variation
verse.repeat(2, vary=["velocity", "register"])
```

### Section Chaining

```python
# Sections auto-chain in order of definition
# Or explicit:
intro.then(verse).then(chorus)
```

---

## Rhythm Notation

Duration syntax supports multiple styles (all equivalent):

### Basic Durations

```python
# Fractions (Pythonic, precise)
1       # Whole note
1/2     # Half note
1/4     # Quarter note
1/8     # Eighth note
1/16    # Sixteenth note

# Named constants (readable)
whole           # 1
half            # 1/2
quarter         # 1/4
eighth          # 1/8
sixteenth       # 1/16

# String shorthand (compact, LilyPond-like)
"1"     # Whole
"2"     # Half
"4"     # Quarter
"8"     # Eighth
"16"    # Sixteenth
```

### Dotted Rhythms

```python
# Function
dot(1/4)        # Dotted quarter = 3/8
dot(1/8)        # Dotted eighth = 3/16

# Named constant
dotted.quarter  # Dotted quarter
dotted.eighth   # Dotted eighth

# String shorthand
"4."            # Dotted quarter
"8."            # Dotted eighth
```

### Tuplets

```python
triplet(1/4)    # Quarter-note triplet
tuplet(5, 1/4)  # Quintuplet in quarter note span
```

### Beat Positions

```python
beat(1)       # Beat 1
beat(2.5)     # Beat 2, second half
beat(3, 1/3)  # Beat 3, first triplet
bar(2).beat(1) # Bar 2, beat 1
```

---

## Key and Scale Notation

### Keys

```python
"C major"
"A minor"
"D dorian"
"F# mixolydian"

Key("C", "major")
Key("A", "minor")
```

### Scales (for melodic patterns)

```python
scale("major")
scale("minor")  # Natural minor
scale("harmonic_minor")
scale("melodic_minor")
scale("dorian")
scale("pentatonic_major")
```

---

## Time Signature Notation

```python
"4/4"
"3/4"
"6/8"
"5/4"
"7/8"

TimeSignature(4, 4)
TimeSignature(6, 8)
```

### Compound Meters

```python
"12/8"  # Compound quadruple
"9/8"   # Compound triple
```

---

## Example: Complete Composition

```python
from pypulang import *

with piece(tempo=110, key="G major", time_sig="4/4", title="Example") as p:

    # Intro
    intro = p.section("intro", bars=4)
    intro.harmony(I, IV)
    intro.track("keys").pattern(arp("up"), rate=1/16)

    # Verse
    verse = p.section("verse", bars=8)
    verse.harmony(I, vi, IV, V)
    verse.track("bass").pattern(root_eighths).octave(-2)
    verse.track("keys").pattern(block_chords, rate=1/2)
    verse.track("melody").notes([
        (D5, 1/4), (E5, 1/4), (G5, 1/2),
        (A5, 1/4), (G5, 1/4), (E5, 1/2),
        # ...
    ])

    # Chorus - transformed from verse
    chorus = verse.transform(
        density=1.3,
        register=+1
    )
    chorus.name = "chorus"
    chorus.harmony(IV, V, I, vi)  # Override harmony

    # Form
    p.form([intro, verse, chorus, verse, chorus])

# Save and play
p.save_midi("example.mid")
p.play()  # Phase 2
```

---

## Reserved for Future

These constructs are planned but not in v0.1:

- `dynamics(...)` — Dynamic markings (p, mf, f, crescendo)
- `articulation(...)` — Staccato, legato, accents
- `expression(...)` — Tempo rubato, ritardando
- `orchestrate(...)` — Multi-instrument assignment
- `counterpoint(...)` — Contrapuntal generation

---

## Error Handling

pyPuLang is strict by default — fail fast on structural errors, warn on unusual choices.

### Errors (Fail Fast)

```python
# Invalid key
piece(key="H major")  # Error: Invalid key

# Invalid time signature
piece(time_sig="5/3")  # Error: Invalid time signature (denominator must be power of 2)

# Harmony doesn't fit section
verse = p.section("verse", bars=7)
verse.harmony(I, IV, vi, V)  # Error: 4 chords don't divide evenly into 7 bars

# Content exceeds declared length
verse = p.section("verse", bars=4)
verse.harmony((I, 2), (IV, 2), (vi, 2), (V, 2))  # Error: 8 bars of harmony in 4-bar section
```

### Warnings

```python
# Track without role specified
verse.track("strings").pattern(block_chords)
# Warning: Track 'strings' has no role specified

# Pattern on unexpected role
verse.track("melody", role=Role.MELODY).pattern(root_eighths)
# Warning: bass pattern on melody track

# Octave inferred from role
verse.track("bass", role=Role.BASS).pattern(root_eighths)
# Warning: octave inferred as 2 from BASS role (use .octave() to silence)
```

### Track Name Capitalization

In pyPuLang, track names can be any string:

```python
verse.track("bass")       # OK
verse.track("Bass")       # OK
verse.track("lead_guitar") # OK
```

However, the standalone puLang syntax requires capitalized track names for parsing clarity. When exporting to puLang (`.pu` files) or Intent IR JSON, track names are automatically normalized:

- `"bass"` → `"Bass"`
- `"lead_guitar"` → `"Lead_guitar"`

This normalization happens on export, so pyPuLang code remains flexible while puLang files are consistent.

---

## Grammar (Informal)

This is not a standalone grammar (pyPuLang is Python-embedded), but the conceptual structure:

```
piece       := "piece" "(" piece_params ")" ":" section*
section     := name "=" piece "." "section" "(" section_params ")" section_body
section_body := (harmony | track | transform)*
harmony     := section "." "harmony" "(" chord_list ")"
track       := section "." "track" "(" name ")" track_body
track_body  := (pattern | notes | modifier)*
pattern     := track "." "pattern" "(" pattern_type ("," pattern_params)* ")"
notes       := track "." "notes" "(" note_list ")"
transform   := section "." "transform" "(" transform_params ")"
```
