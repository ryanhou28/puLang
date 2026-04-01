# puLang Standalone Syntax Specification

*Draft v0.1 — Subject to change*

This document specifies **puLang**, the standalone music-native syntax for the puLang language. puLang is designed for musicians and composers who want to express musical ideas without writing Python.

For the Python-embedded syntax, see [language-spec.md](language-spec.md).

---

## Overview

puLang is a standalone syntax that compiles to the same Intent IR as pyPuLang. Both syntaxes share identical semantics — a piece written in puLang produces the same output as the equivalent pyPuLang code.

### File Extension

puLang files use the `.pu` extension.

### Design Principles

1. **Music-native** — Syntax inspired by lead sheets, chord charts, and ABC notation
2. **Readable** — Minimal punctuation, clean visual hierarchy
3. **Accessible** — No programming experience required
4. **Keyword-delimited** — No braces or enforced indentation; keywords define structure
5. **Compatible** — Identical semantics to pyPuLang

---

## Document Structure

A puLang document has this structure:

```
piece "Title"
  tempo: 120
  key: C
  time: 4/4

define
  theme_a: D5(1/4) E5(1/4) G5(1/2)
  main_harmony: I IV vi V

tracks
  TrackName [role=..., instrument=...]
  ...

section Name [metadata]
  harmony: ...

  TrackName
    property: value
    ...

section Name2 [metadata]
  ...

form: Section1 Section2 Section3 ...
```

Structure is determined by **keywords** (`piece`, `define`, `tracks`, `section`, `form`) and **track names** (capitalized), not by braces or indentation. Indentation is recommended for readability but not required by the parser.

---

## Piece

The top-level container. Everything exists within a piece.

### Syntax

```
piece "Title"
  tempo: 120
  key: C
  time: 4/4
```

The title is optional:

```
piece
  tempo: 120
  key: C
```

### Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `tempo` | number | 120 | Beats per minute |
| `key` | key signature | C | Key signature (see Key Signatures) |
| `time` | time signature | 4/4 | Time signature |

### Example

```
piece "My First Song"
  tempo: 110
  key: G
  time: 4/4
```

Piece properties end when `tracks` or `section` keyword is encountered.

---

## Key Signatures

Key signatures support shorthand for common cases.

### Syntax

```
key: C          # C major (shorthand)
key: G          # G major
key: F#         # F# major

key: Am         # A minor (shorthand with 'm')
key: Cm         # C minor
key: F#m        # F# minor

key: A minor    # A minor (verbose)
key: C minor    # C minor

key: D dorian   # Modes require explicit specification
key: E phrygian
key: F lydian
key: G mixolydian
key: A aeolian  # Same as A minor
key: B locrian
```

### Supported Modes

- `major` (default if omitted)
- `minor` (or `m` shorthand)
- `dorian`
- `phrygian`
- `lydian`
- `mixolydian`
- `aeolian`
- `locrian`

---

## Time Signatures

### Syntax

```
time: 4/4
time: 3/4
time: 6/8
time: 5/4
time: 7/8
time: 12/8
```

---

## Tracks (Piece-Level)

Piece-level track declarations define what tracks exist in the piece, their roles, and default instruments. The `tracks` block is optional — tracks can also be declared inline within sections.

### Syntax

```
tracks
  TrackName [role=role_name, instrument=instrument_name]
  TrackName [role=role_name]
  ...
```

The `tracks` block ends when `section` or `form` is encountered.

### Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `role` | role name | No (but warned if missing) | Musical role: `bass`, `harmony`, `melody`, `rhythm` |
| `instrument` | string or number | No | MIDI instrument name or program number |

### Track Names

Track names must be capitalized (first letter uppercase). This helps distinguish track names from property keywords.

```
# Valid
Bass [role=bass]
Keys [role=harmony]
LeadGuitar [role=melody]

# Invalid - will error
bass [role=bass]
keys [role=harmony]
```

### Roles

| Role | Description |
|------|-------------|
| `bass` | Harmonic foundation, typically lower register |
| `harmony` | Chordal accompaniment |
| `melody` | Primary melodic voice |
| `rhythm` | Rhythmic/percussive elements (drums) |

**Note:** If a role is not specified, a warning is emitted. Roles affect voice leading, octave inference, and pattern validation.

**Rhythm Role:** Tracks with `role=rhythm` are automatically assigned MIDI channel 10 (GM drum channel). They ignore harmony—patterns don't receive chord context.

### Example

```
piece "Jazz Tune"
  tempo: 120
  key: Bb

tracks
  Bass [role=bass, instrument=acoustic_bass]
  Piano [role=harmony, instrument=piano]
  Trumpet [role=melody, instrument=trumpet]
  Drums [role=rhythm, instrument=drums]

section Intro [4 bars]
  ...
```

---

## Sections

Sections are formal units of the piece (verse, chorus, bridge, etc.).

### Syntax

```
section Name [metadata]
  # section content
```

A section ends when the next `section`, `form`, or end of file is encountered.

### Metadata

Section metadata is specified in brackets:

| Metadata | Format | Description |
|----------|--------|-------------|
| `bars` | `N bars` | Section length in bars |
| `beats` | `N beats` | Section length in beats |
| `key` | `key=...` | Override key for this section |
| `time` | `time=...` | Override time signature |

```
section Verse [8 bars]
section Bridge [16 beats]
section Chorus [8 bars, key=C]
section Coda [4 bars, time=3/4]
```

If neither `bars` nor `beats` is specified, length is inferred from harmony.

### Section Names

Section names should be capitalized for consistency.

### Example

```
section Intro [4 bars]
  harmony: I IV

  Keys: pattern: arp(up), rate: 1/16

section Verse [8 bars]
  harmony: I(2) IV(2) vi(2) V(2)

  Bass
    pattern: root_eighths
    octave: -2

  Keys
    pattern: block_chords
```

---

## Harmony

Declares the chord progression for a section using Roman numeral notation.

### Syntax

```
harmony: chord chord chord ...
```

`progression` is an alias for `harmony`:

```
progression: I IV vi V
```

### Roman Numerals

| Symbol | Meaning |
|--------|---------|
| `I, II, III, IV, V, VI, VII` | Major chords on scale degrees |
| `i, ii, iii, iv, v, vi, vii` | Minor chords on scale degrees |

### Chord Modifiers

| Modifier | Meaning | Example |
|----------|---------|---------|
| `7` | Dominant 7th | `V7` |
| `maj7` | Major 7th | `IVmaj7` |
| `min7` | Minor 7th | `ii7` or `iimin7` |
| `.dim` | Diminished | `vii.dim` |
| `.aug` | Augmented | `III.aug` |
| `.sus2` | Suspended 2nd | `I.sus2` |
| `.sus4` | Suspended 4th | `V.sus4` |
| `.add9` | Add 9th | `I.add9` |
| `.inv(n)` | Inversion (0, 1, 2) | `I.inv(1)` |

### Secondary Dominants

```
V/V     # V of V
V/vi    # V of vi
V7/IV   # V7 of IV
```

### Chord Duration

By default, chords divide equally across the section. To specify explicit durations (in bars), use parentheses:

```
# Equal duration: each chord gets 2 bars in an 8-bar section
harmony: I IV vi V

# Explicit duration in bars
harmony: I(2) IV(2) vi(2) V(2)

# Mixed durations
harmony: I(4) IV(2) V(2)

# Single bar each
harmony: I(1) IV(1) vi(1) V(1) I(1) IV(1) V(1) I(1)
```

### Separators

Both whitespace and commas are supported:

```
harmony: I IV vi V
harmony: I, IV, vi, V
harmony: I(2), IV(2), vi(2), V(2)
```

### Examples

```
# Simple pop progression
harmony: I V vi IV

# With durations
harmony: I(2) IV(1) vi(1) V(4)

# Jazz turnaround
harmony: IVmaj7 V7/V V7 I

# With modifiers
harmony: I IVmaj7 vi.inv(1) V7.sus4 V7 I
```

---

## Section-Level Tracks

Within a section, tracks define what each instrument plays.

### Existing Tracks (Multi-line)

For tracks declared at piece-level (or previously), use the track name followed by a colon on its own line:

```
TrackName:
  property: value
  property: value
```

Or without the colon (track name alone):

```
TrackName
  property: value
  property: value
```

A track block ends when another track name, `section`, or `form` is encountered.

### Existing Tracks (One-liner)

Properties can be on a single line after the track name with colon:

```
TrackName: property: value, property: value
TrackName: property: value property: value
```

Commas between properties are optional on one-liners.

### New Track Declaration

To declare a new track within a section (not at piece-level), use the `track` keyword:

```
track TrackName [role=..., instrument=...]
  property: value
  property: value
```

Or one-liner:

```
track TrackName [role=..., instrument=...]: property: value, property: value
```

### Track Properties

| Property | Type | Description |
|----------|------|-------------|
| `pattern` | pattern name | Pattern generator to use |
| `rate` | fraction | Note rate (1/4, 1/8, 1/16) |
| `octave` | integer | Octave shift from default |
| `velocity` | 0-127 | MIDI velocity |
| `dynamics` | dynamic marking | Musical dynamics (see below) |
| `notes` | note list | Literal notes (escape hatch) |

### Velocity vs Dynamics

These are mutually exclusive — specify one or the other, not both.

**Velocity:** Direct MIDI value (0-127)
```
Bass: pattern: root_quarters, velocity: 100
```

**Dynamics:** Musical dynamics, mapped to velocity ranges
```
Bass: pattern: root_quarters, dynamics: mf
```

| Dynamic | Velocity Range |
|---------|---------------|
| `pp` | 20-40 |
| `p` | 40-60 |
| `mp` | 60-75 |
| `mf` | 75-90 |
| `f` | 90-110 |
| `ff` | 110-127 |

### Property Inheritance

Section-level tracks inherit properties from piece-level declarations. Section properties override piece-level defaults.

```
tracks
  Bass [role=bass, instrument=acoustic_bass]

section Verse [8 bars]
  Bass
    pattern: root_eighths
    # Inherits instrument from piece-level

section Chorus [8 bars]
  Bass
    pattern: root_quarters
    octave: -1  # Can override defaults
```

### Silent Tracks

If a track is not mentioned in a section, it is silent for that section.

```
section Intro [4 bars]
  harmony: I IV

  Keys: pattern: arp(up)
  # Bass is silent in intro

section Verse [8 bars]
  harmony: I IV vi V

  Bass: pattern: root_eighths  # Bass enters
  Keys: pattern: block_chords
```

### Examples

```
section Verse [8 bars]
  harmony: I(2) IV(2) vi(2) V(2)

  # Multi-line format
  Bass
    pattern: root_eighths
    octave: -2
    dynamics: mf

  # One-liner format
  Keys: pattern: block_chords, rate: 1/2

  # Melody with literal notes
  Melody
    notes: D5(1/4) E5(1/4) G5(1/2) rest(1/4) A5(quarter) G5(4) E5(2)
```

---

## Patterns

Patterns are generators that produce notes from harmony context.

### Syntax

```
pattern: pattern_name
pattern: pattern_name(parameter)
pattern: pattern_name(param1, param2)
```

### Built-in Patterns

| Pattern | Description |
|---------|-------------|
| `root_quarters` | Root note in quarter notes |
| `root_eighths` | Root note in eighth notes |
| `root_fifths` | Root + fifth alternating |
| `walking_bass` | Jazz-style walking bass |
| `block_chords` | Block chord hits |
| `arp(direction)` | Arpeggio with direction |
| `alberti` | Alberti bass pattern |
| `sustained` | Sustained/held notes |

### Arpeggio Directions

```
pattern: arp(up)      # Ascending
pattern: arp(down)    # Descending
pattern: arp(updown)  # Ascending then descending
pattern: arp(random)  # Random order
```

### Pattern Parameters

Additional parameters via track properties:

```
Keys
  pattern: arp(up)
  rate: 1/16        # Sixteenth notes
  octave: 1         # One octave up
```

---

## Drums and Percussion

Drums use the same track infrastructure with drum-specific patterns and notation.

### Drum Patterns

```
Drums [role=rhythm]
  pattern: rock_beat

Drums [role=rhythm]
  pattern: four_on_floor(hihat=open)

Drums: pattern: shuffle, swing: 0.67
```

#### Built-in Drum Patterns

| Pattern | Description |
|---------|-------------|
| `rock_beat` | Kick on 1/3, snare on 2/4, hihats on 8ths |
| `four_on_floor` | Kick on every beat (dance/electronic) |
| `backbeat` | Snare on 2/4 only |
| `eighth_hats` | Hi-hat eighth notes only |
| `shuffle` | Swung feel with kick/snare |

### Literal Drum Notes

Use drum sound names with the `notes` property:

```
Drums [role=rhythm]
  notes: kick(1/4) hihat(1/8) hihat(1/8) snare(1/4) hihat(1/8) hihat(1/8)
```

#### Drum Sound Names

| Sound | Aliases | GM Note |
|-------|---------|---------|
| `kick` | `bass_drum`, `bd` | 36 |
| `kick2` | `bass_drum2` | 35 |
| `snare` | `sd` | 38 |
| `snare2` | | 40 |
| `rimshot` | `rim` | 37 |
| `clap` | `handclap` | 39 |
| `hihat` | `hh`, `hihat_closed` | 42 |
| `hihat_open` | `hho` | 46 |
| `hihat_pedal` | `hhp` | 44 |
| `tom_low` | `tom_l` | 45 |
| `tom_mid` | `tom_m` | 47 |
| `tom_high` | `tom_h` | 50 |
| `crash` | | 49 |
| `crash2` | | 57 |
| `ride` | | 51 |
| `ride_bell` | | 53 |
| `tambourine` | `tamb` | 54 |
| `cowbell` | | 56 |
| `shaker` | | 70 |

### Grid Notation

For complex drum patterns, use the `drums` block with grid notation:

```
section Verse [8 bars]
  harmony: I IV vi V

  drums [grid=1/16]
    kick:        x...x...x...x...
    snare:       ....x.......x...
    hihat:       x.x.x.x.x.x.x.x.
    hihat_open:  ..............x.
```

#### Grid Characters

| Char | Meaning |
|------|---------|
| `x` | Normal hit |
| `.` | Rest |
| `o` | Accent (higher velocity) |
| `-` | Ghost note (lower velocity) |

The grid length represents one bar. Grid resolution is set by the `grid` parameter (default: 1/16 for 16 characters per bar in 4/4).

#### Grid Notation Example

```
piece "Rock Song"
  tempo: 120
  key: C

tracks
  Bass [role=bass]
  Drums [role=rhythm]

section Verse [8 bars]
  harmony: I(2) IV(2) vi(2) V(2)

  Bass: pattern: root_eighths, octave: -2

  drums [grid=1/16]
    kick:   x...x...x.x.x...
    snare:  ....x.......x...
    hihat:  x.x.x.x.x.x.x.x.

section Chorus [8 bars]
  harmony: IV V I vi

  Bass: pattern: root_quarters, octave: -2

  drums [grid=1/16]
    kick:   x.x.x.x.x.x.x.x.
    snare:  ....x.......x...
    hihat:  xxxxxxxxxxxxxxxx
    crash:  x...............   # Crash on beat 1
```

---

## Literal Notes (Escape Hatch)

When patterns don't suffice, use literal notes.

### Syntax

```
notes: pitch(duration) pitch(duration) ...
```

### Pitch Notation

```
C4    # Middle C (MIDI 60)
D5    # D in octave 5
F#4   # F sharp 4
Bb3   # B flat 3
```

### Duration Notation

Multiple formats supported inside parentheses:

| Format | Example | Meaning |
|--------|---------|---------|
| Fraction | `C4(1/4)` | Quarter note |
| Fraction | `C4(3/8)` | Dotted quarter |
| Named | `C4(quarter)` | Quarter note |
| Named | `C4(half)` | Half note |
| Named | `C4(dotted.quarter)` | Dotted quarter |
| Shorthand | `C4(4)` | Quarter note (4 = 1/4) |
| Shorthand | `C4(8)` | Eighth note |
| Shorthand | `C4(4.)` | Dotted quarter |

### Named Durations

| Name | Value |
|------|-------|
| `whole` | 1 |
| `half` | 1/2 |
| `quarter` | 1/4 |
| `eighth` | 1/8 |
| `sixteenth` | 1/16 |
| `dotted.half` | 3/4 |
| `dotted.quarter` | 3/8 |
| `dotted.eighth` | 3/16 |

### Rests

```
rest(1/4)     # Quarter rest
rest(quarter) # Quarter rest
rest(4)       # Quarter rest
```

### Chords (Simultaneous Notes)

```
chord(C4, E4, G4)(1/2)  # C major triad, half note
```

### Velocity per Note

```
notes: C4(1/4, v=80) D4(1/4, v=90) E4(1/2, v=100)
```

### Articulation (Future)

```
notes: C4(1/4, staccato) D4(1/4, legato) E4(1/2, accent)
```

### Examples

```
Melody
  notes: D5(1/4) E5(1/4) G5(1/2) rest(1/4) A5(quarter) G5(4) E5(2)

Melody
  notes: C4(1/4, v=80) D4(eighth) E4(1/4) F#4(dotted.quarter) G4(1/8)
```

---

## Form

Specifies the order in which sections are played.

### Syntax

```
form: Section1 Section2 Section3 ...
```

Whitespace-separated section names.

### Example

```
piece "Pop Song"
  tempo: 120
  key: C

section Intro [4 bars]
  ...

section Verse [8 bars]
  ...

section Chorus [8 bars]
  ...

section Bridge [4 bars]
  ...

section Outro [4 bars]
  ...

form: Intro Verse Chorus Verse Chorus Bridge Chorus Chorus Outro
```

If `form` is omitted, sections play in the order they are defined.

---

## Definitions and Variables

puLang supports reusable definitions for melodies, harmonies, and other musical elements. This allows you to define a theme once and use it across multiple sections and tracks.

*Note: This feature is specified for a future implementation phase.*

### Define Block

Use the `define` block to declare reusable elements at the piece level:

```
piece "Sonata"
  tempo: 120
  key: C

define
  # Melodies
  theme_a: D5(1/4) E5(1/4) G5(1/2) A5(1/4) G5(1/4) E5(1/2)
  theme_b: C5(1/2) B4(1/4) A4(1/4) G4(1/2)

  # Harmonies
  main_progression: I(2) IV(2) vi(2) V(2)
  bridge_progression: vi IV I V

tracks
  Violin [role=melody]
  Piano [role=harmony]

section Exposition [8 bars]
  harmony: @main_progression

  Violin
    notes: @theme_a

section Development [8 bars]
  harmony: @bridge_progression

  Violin
    notes: @theme_b
```

### Reference Syntax

Use `@name` to reference a defined element:

```
harmony: @main_progression
notes: @theme_a
```

### Inline Definitions

You can also define elements inline using `as @name`:

```
section Verse [8 bars]
  # Define and use in one line
  harmony: I IV vi V as @verse_harmony

  Melody
    notes: D5(1/4) E5(1/4) G5(1/2) as @verse_melody

section Chorus [8 bars]
  # Reuse the inline-defined elements
  harmony: @verse_harmony

  Strings
    notes: @verse_melody
    octave: 1
```

### Naming Rules

- Variable names are **not** case-sensitive enforced (unlike track names)
- Any of these are valid: `@ThemeA`, `@themeA`, `@theme_a`, `@THEME_A`
- Names must start with a letter and contain only letters, numbers, and underscores

### Scope

All definitions have **global scope** — they can be used anywhere in the piece after being defined.

```
define
  my_theme: C4(1/4) D4(1/4) E4(1/2)

section Intro [4 bars]
  harmony: I IV as @intro_harmony  # Inline definition

  Piano
    notes: @my_theme  # Use define block variable

section Verse [8 bars]
  harmony: @intro_harmony  # Use inline-defined variable from Intro

  Piano
    notes: @my_theme
```

### Redefinition Error

Redefining a variable is an error:

```
define
  theme: C4(1/4) D4(1/4)

section Verse [8 bars]
  harmony: I IV vi V as @theme  # Error: '@theme' is already defined
```

### What Can Be Defined

| Type | Example |
|------|---------|
| Melodies/Notes | `melody_a: D5(1/4) E5(1/4) G5(1/2)` |
| Harmonies | `verse_chords: I IV vi V` |
| Harmony with durations | `jazz_changes: IVmaj7(2) V7(2) I(4)` |

### pyPuLang Equivalent

In pyPuLang, use standard Python variables:

```python
theme_a = [(D5, 1/4), (E5, 1/4), (G5, 1/2)]
verse_harmony = [I, IV, vi, V]

with piece(tempo=120, key="C") as p:
    verse = p.section("verse", bars=8)
    verse.harmony(*verse_harmony)
    verse.track("violin").notes(theme_a)

    chorus = p.section("chorus", bars=8)
    chorus.track("strings").notes(theme_a)  # Reuse
```

---

## Comments

Single-line comments use `#`:

```
piece "Example"
  tempo: 120  # BPM

# This is a comment
section Verse [8 bars]
  harmony: I IV vi V  # Classic progression
```

Multi-line comments are not supported in v0.1.

---

## Complete Example

```
piece "Summer Breeze"
  tempo: 110
  key: G
  time: 4/4

# Define tracks for the piece
tracks
  Bass [role=bass, instrument=acoustic_bass]
  Piano [role=harmony, instrument=piano]
  Melody [role=melody, instrument=flute]
  Drums [role=rhythm]

section Intro [4 bars]
  harmony: I IV

  Piano: pattern: arp(up), rate: 1/16
  # Bass, Melody, and Drums are silent

section Verse [8 bars]
  harmony: I(2) IV(2) vi(2) V(2)

  Bass
    pattern: root_eighths
    octave: -2
    dynamics: mp

  Piano
    pattern: block_chords
    rate: 1/2

  Melody
    notes: D5(1/4) E5(1/4) G5(1/2) rest(1/4) A5(1/4) G5(1/4) E5(1/2)
           rest(1/4) D5(1/4) E5(1/4) D5(1/2) rest(1/4) B4(1/4) D5(1/2)

  # Drums with grid notation
  drums [grid=1/16]
    kick:   x...x...x...x...
    snare:  ....x.......x...
    hihat:  x.x.x.x.x.x.x.x.

section Chorus [8 bars]
  progression: IV V I vi IV V I I  # 'progression' is alias for 'harmony'

  Bass
    pattern: root_quarters
    octave: -2
    dynamics: mf

  Piano
    pattern: block_chords
    rate: 1/4
    dynamics: f

  # Drums with pattern (simpler than grid)
  Drums: pattern: rock_beat(fills=true)

section Bridge [4 bars]
  harmony: vi(2) IV(2)

  # Introduce strings just for bridge
  track Strings [role=harmony, instrument=strings]
    pattern: sustained
    octave: 1
    dynamics: mp

  Bass: pattern: root_quarters, octave: -2

  # Lighter drums for bridge
  drums [grid=1/16]
    kick:   x.......x.......
    snare:  ........x.......
    hihat:  x...x...x...x...

section Outro [4 bars]
  harmony: I(2) IV(1) I(1)

  Piano: pattern: arp(down), rate: 1/8, dynamics: p
  # No drums in outro

form: Intro Verse Chorus Verse Chorus Bridge Chorus Outro
```

---

## How the Parser Works

puLang uses **keyword-delimited parsing**, not braces or enforced indentation.

### Structural Keywords

| Keyword | Starts | Ends when |
|---------|--------|-----------|
| `piece` | Piece definition | End of file |
| `define` | Definition block | `tracks`, `section`, or `form` |
| `tracks` | Track declarations | `section` or `form` |
| `section` | Section definition | Next `section`, `form`, or EOF |
| `drums` | Drum grid block | Next track, `section`, `form`, or EOF |
| `form` | Form definition | End of line |

### Track Detection

Within a section:
- A **capitalized name** alone or followed by `:` starts a track block
- The `track` keyword starts a new track declaration
- Track block ends at next track name, `section`, `form`, or EOF

### Property Detection

- Properties use `name: value` syntax
- Property names are lowercase: `pattern`, `octave`, `rate`, `velocity`, `dynamics`, `notes`, `harmony`, `progression`
- Track names are capitalized: `Bass`, `Keys`, `Melody`

This distinction allows unambiguous parsing without braces.

---

## Error Handling

puLang is strict — fail fast on structural errors, warn on unusual choices.

### Errors (Fatal)

```
# Invalid key
key: H major  # Error: Invalid key root 'H'

# Invalid time signature
time: 5/3  # Error: Denominator must be power of 2

# Harmony doesn't fit section
section Verse [7 bars]
  harmony: I IV vi V  # Error: 4 chords don't divide evenly into 7 bars

# Unknown track reference
section Verse [8 bars]
  Unknown: pattern: root_quarters  # Error: Track 'Unknown' not declared

# Uncapitalized track name
track bass [role=bass]  # Error: Track name must be capitalized

# Both velocity and dynamics specified
Bass: pattern: root_quarters, velocity: 100, dynamics: mf  # Error
```

### Warnings

```
# Track without role
track Keys  # Warning: Track 'Keys' has no role specified

# Pattern mismatch with role
Melody [role=melody]: pattern: root_eighths
# Warning: Bass pattern on melody track
```

---

## Grammar (Informal)

```
document     = piece

piece        = "piece" [string] NEWLINE piece_body
piece_body   = piece_props [define_block] [tracks_block] sections [form_line]

piece_props  = (prop_line)*
prop_line    = PROP_NAME ":" value NEWLINE

define_block = "define" NEWLINE (definition)*
definition   = VAR_NAME ":" value NEWLINE

tracks_block = "tracks" NEWLINE (track_decl)*
track_decl   = TRACK_NAME "[" attributes "]" NEWLINE

sections     = section+
section      = "section" NAME "[" section_meta "]" NEWLINE section_body
section_meta = (bars | beats) ("," section_override)*
section_body = [harmony_line] (section_track | drums_block)*

harmony_line = ("harmony" | "progression") ":" chord_list ["as" VAR_REF] NEWLINE
chord_list   = chord (","? chord)* | VAR_REF
chord        = ROMAN [modifiers] ["(" duration ")"]

section_track = track_ref | track_decl_inline
track_ref     = TRACK_NAME [":"] (one_liner | multi_line)
one_liner     = track_props NEWLINE
multi_line    = NEWLINE (INDENT track_prop NEWLINE)+
track_props   = track_prop (","? track_prop)*
track_prop    = PROP_NAME ":" (value | VAR_REF) ["as" VAR_REF]

track_decl_inline = "track" TRACK_NAME "[" attributes "]" [":"] track_body

drums_block  = "drums" "[" drums_meta "]" NEWLINE (drum_lane)+
drums_meta   = "grid" "=" duration
drum_lane    = DRUM_NAME ":" GRID_PATTERN NEWLINE
DRUM_NAME    = "kick" | "snare" | "hihat" | "hihat_open" | "crash" | ...
GRID_PATTERN = [x.\-o]+

form_line    = "form" ":" NAME+ NEWLINE

VAR_NAME     = ALPHA (ALNUM | "_")*
VAR_REF      = "@" VAR_NAME
TRACK_NAME   = UPPER ALNUM*
PROP_NAME    = LOWER ALNUM*
NAME         = ALPHA ALNUM*
ROMAN        = [b#]? ("I" | "II" | "III" | "IV" | "V" | "VI" | "VII" |
                      "i" | "ii" | "iii" | "iv" | "v" | "vi" | "vii")
```

---

## Relationship to pyPuLang

puLang and pyPuLang are two syntaxes for the same language. They share:

- The same Intent IR
- The same semantics
- The same transform pipeline
- The same backends

### Conversion

A `.pu` file can be compiled to Intent IR:
```
pulang compile song.pu -o song.ir.json
```

pyPuLang can export to Intent IR:
```python
p.to_ir().save("song.ir.json")
```

Both produce identical IR for equivalent compositions.

### Naming Convention

When converting from pyPuLang to puLang, track names are normalized to capitalized form:
- `"bass"` → `"Bass"`
- `"lead_guitar"` → `"Lead_guitar"`

---

## Comparison with Other Formats

### vs ABC Notation
ABC uses single-letter field codes (`X:`, `T:`, `M:`). puLang uses full keywords (`piece`, `section`, `harmony`) for clarity.

### vs LilyPond
LilyPond uses braces `{ }` for grouping musical phrases. puLang avoids braces for a cleaner, less code-like appearance.

### vs Alda
Alda uses `instrument:` followed by notes. puLang separates structure (`section`) from content (`harmony`, tracks) more explicitly.

---

## Future Extensions

These are planned but not in v0.1:

- Multi-line comments (`/* ... */`)
- Subsections (nested section structure)
- Imports (`import "patterns.pu"`)
- Inline transforms (`Chorus = Verse.transform(transpose: 5)`)
- Dynamics markings (`crescendo`, `decrescendo`)
- Articulations (`staccato`, `legato`, `accent`)
- Tempo changes within piece
- Repeat signs (`repeat 2x: ...`)

*Note: Definitions and variables (`define` block, `@references`) are specified above but targeted for a future implementation phase.*
