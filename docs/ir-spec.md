# puLang IR Specification

*Draft — Three-tier IR with Dialect Framework*

---

## Overview

puLang uses a **three-tier IR architecture** built on a **dialect framework** inspired by MLIR. Rather than hardcoding fixed IR levels, puLang provides infrastructure for defining **dialects** — named collections of operations and types that represent music at different levels of abstraction — along with **passes** (analysis and transformation) and **lowering** (dialect-to-dialect conversion).

The three standard dialects shipped with puLang are:

1. **Intent IR** — Captures compositional intent (harmony, form, patterns, roles)
2. **Score IR** — Captures realized musical content (specific pitches, voices, articulations, dynamics)
3. **Event IR** — Captures concrete performance events (MIDI-like note-on/off, absolute timing)

### Why Three Tiers?

There is a large semantic gap between compositional intent ("play a I-IV-V-I with arpeggiated piano") and performance events ("MIDI note 60 at beat 0 for 0.25 beats at velocity 100"). Jumping directly between these levels flattens an entire layer of musical decision-making:

- **Voice leading**: How does the soprano move from chord to chord?
- **Voicing**: Close or open position? What register? What doubling?
- **Counterpoint**: How do the voices relate to each other?
- **Melodic contour**: Shape, direction, intervallic content
- **Articulation and expression**: Legato, staccato, dynamics — not just "what notes" but "how they're shaped"

This is where **music theory actually lives**. A musicologist analyzing a Bach chorale doesn't think in terms of "the composer intended I-IV-V-I" (too abstract) or "MIDI note 67 at beat 3" (too concrete). They think in terms of **specific pitches in specific voices with specific relationships to each other** — organized by bar, beat, and voice, not by absolute time and MIDI number.

Score IR captures this middle layer explicitly.

### The Dialect Framework

Beyond the three standard dialects, puLang's architecture is designed as a **framework for defining musical dialects**. Different musical traditions, analytical methods, and compositional techniques may warrant their own dialect:

- A Schenkerian analyst needs structural levels (background, middleground, foreground)
- A jazz musician needs lead sheet conventions, comping patterns, walking bass idioms
- A set theorist needs pitch class sets, interval vectors, transformational networks
- A Baroque performer needs figured bass realization rules, ornament tables

Rather than trying to hardcode all of these, puLang provides the infrastructure — operation base types, a type system, pass infrastructure, dialect registry, and lowering/lifting framework — and lets dialects be defined on top.

```
┌─────────────────────────────────────────────────────────────────┐
│                    puLang Dialect Framework                      │
│                                                                 │
│  Core infrastructure:                                           │
│  - Operation base types (every musical "thing" is an operation) │
│  - Type system (pitch, duration, interval, dynamics, ...)       │
│  - Pass infrastructure (analysis + transform)                   │
│  - Dialect registry                                             │
│  - Lowering / lifting framework (dialect ↔ dialect conversion)  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Standard Dialects (shipped with puLang)       │  │
│  │                                                           │  │
│  │  intent.*   — Harmony, form, patterns, roles              │  │
│  │  score.*    — Voices, concrete pitches, articulation,     │  │
│  │               dynamics, phrasing                          │  │
│  │  event.*    — MIDI-like performance events, absolute time │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Analytical Dialects (future / community)      │  │
│  │                                                           │  │
│  │  schenkerian.*  — Structural levels, Ursatz, prolongation │  │
│  │  settheory.*    — Pitch class sets, interval vectors      │  │
│  │  counterpoint.* — Species rules, voice independence       │  │
│  │  rhythm.*       — Metric hierarchy, grouping structure    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Style Dialects (future / community)           │  │
│  │                                                           │  │
│  │  jazz.*       — Lead sheets, comping, walking bass idioms │  │
│  │  baroque.*    — Figured bass, ornament tables, continuo   │  │
│  │  spectral.*   — Frequency content, partials, timbre       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Two Syntaxes, One IR

puLang has two distinct frontend syntaxes that both emit identical Intent IR:

| Syntax | Description | File Type | Target Users |
|--------|-------------|-----------|--------------|
| **pyPuLang** | Python-embedded DSL with context managers and method chaining | `.py` | Programmers, AI/ML researchers |
| **puLang** | Standalone music-native syntax, inspired by sheet music | `.pu` | Musicians, composers |

### Full Pipeline

```
┌──────────────────┐     ┌──────────────────┐
│    pyPuLang      │     │     puLang       │
│  (Python DSL)    │     │  (Standalone)    │
│   .py files      │     │   .pu files      │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         └──────────┬─────────────┘
                    ▼
            ┌───────────────┐
            │   Intent IR   │ ← intent-level passes (analysis & transform)
            │  (JSON file)  │
            └───────┬───────┘
                    │ lowering (voicing, voice leading, realization)
                    ▼
            ┌───────────────┐
            │   Score IR    │ ← score-level passes (analysis & transform)
            │  (JSON file)  │
            └───────┬───────┘
                    │ lowering (performance interpretation)
                    ▼
            ┌───────────────┐
            │   Event IR    │ ← event-level passes (analysis & transform)
            │  (JSON file)  │
            └───────┬───────┘
                    ▼
            ┌───────────────┐
            │   Backends    │
            │  (MIDI, etc.) │
            └───────────────┘
```

The IR is the **interchange format** — pyPuLang builds it in-memory, puLang will parse `.pu` files to produce it, and tools can read/write it as JSON.

---

## Design Principles

1. **Serializable** — All IR serializes to JSON
2. **Language-agnostic** — No Python-specific constructs in the IR
3. **Semantically clear** — A `Chord` means a chord, not "some notes"
4. **Immutable transforms** — Transforms return new IR, don't mutate
5. **Minimal** — Only include what's necessary; extend later
6. **Multi-level** — Each dialect captures music at its natural level of abstraction
7. **Bidirectional** — Passes can go down (lowering/realization) *and* up (lifting/analysis)
8. **Extensible** — New dialects, passes, and lowering rules can be added without modifying core

---

## Key Design Decisions

### Serialization Format: JSON

- Human-readable for debugging and AI interop
- Universal tooling support
- Fractions as strings: `"3/4"`, `"1/16"`
- Type discriminators: `{"type": "note", ...}`

### Timing Representation

| IR Layer | Representation | Example | Rationale |
|----------|----------------|---------|-----------|
| Intent IR | Abstract (bar counts, beat durations) | `"duration": "2"` (bars) | Matches compositional thinking |
| Score IR | Bar-relative | `{"bar": 2, "beat": "3/2"}` | Matches musical thinking — "beat 3 of bar 2" |
| Event IR | Piece-relative | `{"start": "13/2"}` | Simple math for backends |

### Pitch Representation

| IR Layer | Representation | Example | Rationale |
|----------|----------------|---------|-----------|
| Intent IR | Roman numerals / patterns | `"numeral": "V"` | Abstract, key-independent |
| Score IR | Scientific notation | `"C#4"` | Human-readable, preserves enharmonic spelling |
| Event IR | MIDI integer | `61` | Direct backend mapping |

---

## Passes Infrastructure

Passes are the core mechanism for analyzing and transforming music at any IR level. A pass takes IR as input and returns either analysis results or transformed IR.

### Pass Types

1. **Analysis passes** — Read IR, produce analysis results (do not modify IR)
2. **Transform passes** — Read IR, produce new IR (immutable — original unchanged)
3. **Lowering passes** — Convert from a higher-level dialect to a lower-level one
4. **Lifting passes** — Convert from a lower-level dialect to a higher-level one (analysis/reverse-engineering)

### Passes at Each Dialect Level

#### Intent-Level Passes

Analysis:
- **Harmonic function analysis** — Classify each chord's tonal function (tonic, predominant, dominant)
- **Form analysis** — Detect formal structures (binary, ternary, sonata, rondo, verse-chorus)
- **Harmonic rhythm analysis** — Measure how fast chords change relative to meter
- **Modulation detection** — Identify key center shifts and pivot chords
- **Tonal center tracking** — Track the perceived key across sections

Transform:
- **Reharmonize** — Substitute chords using strategies (modal interchange, tritone substitution, secondary dominants, diatonic substitution)
- **Transpose** — Shift key center by interval
- **Modulate** — Introduce key change at a specific point with pivot chord
- **Restructure** — Reorder, duplicate, or remove sections
- **Change pattern** — Swap pattern types on tracks

#### Score-Level Passes

Analysis:
- **Voice leading analysis** — Check for parallel fifths/octaves, unresolved tendency tones, voice crossing
- **Counterpoint analysis** — Identify species, evaluate voice independence, measure dissonance treatment
- **Melodic contour analysis** — Classify shape (arch, descending, ascending, wave), measure intervallic content
- **Texture analysis** — Classify as homophonic, polyphonic, monophonic, homorhythmic; measure density
- **Range analysis** — Check each voice against standard ranges (SATB, instrument ranges)
- **Register analysis** — Measure spacing between voices, identify registral gaps
- **Harmonic interval analysis** — Evaluate vertical sonority at each beat

Transform:
- **Voice leading optimization** — Minimize voice movement, resolve tendency tones, avoid forbidden parallels
- **Add ornamentation** — Insert passing tones, neighbor tones, suspensions, anticipations
- **Apply articulation** — Add staccato, legato, accents based on style rules
- **Adjust dynamics** — Apply dynamic curves, phrasing dynamics
- **Change voicing** — Switch between close, open, drop-2, spread voicings
- **Reduce texture** — Remove inner voices, simplify doublings
- **Orchestrate** — Assign voices to specific instruments with idiomatic adjustments

#### Event-Level Passes

Analysis:
- **Groove analysis** — Measure timing deviations from the grid, identify swing ratio
- **Dynamics analysis** — Velocity curves, dynamic range, accent patterns
- **Articulation detection** — Infer staccato vs legato from note overlap and duration
- **Density analysis** — Notes per beat, polyphonic density over time

Transform:
- **Humanize** — Add subtle timing and velocity variations to sound less mechanical
- **Quantize** — Snap events to a rhythmic grid
- **Apply swing** — Offset alternating subdivisions by a swing ratio
- **Compress dynamics** — Narrow or expand the velocity range
- **Time-stretch** — Scale all timings by a factor

### Lowering as Musicological Statement

The lowering process between dialects is not just mechanical conversion — it encodes musicological knowledge and stylistic conventions. Different lowering strategies represent different approaches to music-making:

**Intent → Score lowering** encodes:
- Voice leading pedagogy (how to connect chords smoothly)
- Voicing conventions (register, spacing, doubling rules)
- Pattern realization (how an "arpeggio" pattern becomes specific notes)
- Style-period norms (Baroque continuo realization vs. jazz voicings vs. Romantic part-writing)

**Score → Event lowering** encodes:
- Performance practice (how notation maps to actual sound)
- Tempo interpretation (rubato, agogic accents)
- Articulation conventions (how long is "staccato"? how connected is "legato"?)
- Dynamic mapping (what velocity is "forte"?)

By making these processes explicit and configurable, puLang makes musicological decisions **visible and debatable** — exactly what scholars, educators, and composers need.

### Lifting as Analysis

Passes can also go **up** (lifting) — this is what musicologists do when they analyze music:

- **Event → Score lifting** (transcription): Infer notation from performance data
- **Score → Intent lifting** (harmonic analysis): Infer Roman numeral analysis from specific pitches
- **Score → analytical dialect**: Perform Schenkerian reduction, set-theoretic analysis, etc.

Lifting is inherently lossy and interpretive — there may be multiple valid analyses of the same music. This is a feature, not a bug: different analytical frameworks are different "liftings" to different dialects, and disagreement between them is musicologically meaningful.

---

## Standard Dialect: Intent IR

Module: `pulang.ir.intent`

Intent IR captures **what the composer wants** — harmonic structure, formal design, textural intent — without specifying exactly how it should sound. This is the level at which composition-as-planning happens.

### Piece

The top-level container.

```python
@dataclass
class Piece:
    title: str | None
    tempo: float              # BPM
    key: Key
    time_signature: TimeSignature
    sections: list[Section]
    form: list[str] | None    # Section names in order, or None for linear
```

**JSON Schema:**
```json
{
  "type": "piece",
  "title": "Example",
  "tempo": 120,
  "key": {"root": "C", "mode": "major"},
  "time_signature": {"numerator": 4, "denominator": 4},
  "sections": [...],
  "form": ["intro", "verse", "chorus", "verse", "chorus"]
}
```

---

### Key

```python
@dataclass
class Key:
    root: str       # "C", "F#", "Bb", etc.
    mode: str       # "major", "minor", "dorian", etc.
```

**JSON:**
```json
{"root": "D", "mode": "major"}
```

---

### TimeSignature

```python
@dataclass
class TimeSignature:
    numerator: int
    denominator: int
```

**JSON:**
```json
{"numerator": 6, "denominator": 8}
```

---

### Section

```python
@dataclass
class Section:
    name: str
    bars: int
    key: Key | None             # Override, or None to inherit
    time_signature: TimeSignature | None
    harmony: Harmony
    tracks: list[Track]
```

**JSON:**
```json
{
  "type": "section",
  "name": "verse",
  "bars": 8,
  "key": null,
  "time_signature": null,
  "harmony": {...},
  "tracks": [...]
}
```

---

### Harmony

A sequence of chord changes.

```python
@dataclass
class ChordChange:
    chord: Chord
    duration: str           # Fraction as string, e.g. "1/4", "2"

@dataclass
class Harmony:
    changes: list[ChordChange]
    duration_unit: str      # "bars" or "beats"
```

**JSON:**
```json
{
  "type": "harmony",
  "duration_unit": "bars",
  "changes": [
    {"chord": {"numeral": "I", "quality": "major"}, "duration": "2"},
    {"chord": {"numeral": "IV", "quality": "major"}, "duration": "2"},
    {"chord": {"numeral": "vi", "quality": "minor"}, "duration": "2"},
    {"chord": {"numeral": "V", "quality": "major", "extensions": ["7"]}, "duration": "2"}
  ]
}
```

---

### Chord

```python
@dataclass
class Chord:
    numeral: str            # "I", "ii", "V", etc.
    quality: str            # "major", "minor", "diminished", "augmented"
    extensions: list[str]   # ["7", "9", "sus4"], etc.
    inversion: int          # 0 = root, 1 = first, 2 = second
    altered_root: int       # 0 = natural, -1 = flat, +1 = sharp (for bVII, etc.)
    secondary: str | None   # "V" for V/V, "vi" for V/vi, etc.
    special_type: str | None  # "neapolitan", "italian6", etc. (future)
```

**JSON:**
```json
{
  "numeral": "V",
  "quality": "major",
  "extensions": ["7"],
  "inversion": 0,
  "altered_root": 0,
  "secondary": null,
  "special_type": null
}
```

**Borrowed chord example (bVII):**
```json
{
  "numeral": "VII",
  "quality": "major",
  "extensions": [],
  "inversion": 0,
  "altered_root": -1,
  "secondary": null,
  "special_type": null
}
```

---

### Track

```python
@dataclass
class Track:
    name: str
    role: str | None        # "melody", "bass", "harmony", "rhythm", or None
    instrument: str | int   # Name or MIDI program number
    content: Pattern | Notes
    octave_shift: int       # Relative octave adjustment
    velocity: int           # Base velocity (0-127)
    muted: bool
```

**Note:** `role` can be `None` if not specified. A warning is emitted during lowering if role is not set.

**JSON:**
```json
{
  "type": "track",
  "name": "Bass",
  "role": "bass",
  "instrument": "acoustic_bass",
  "content": {...},
  "octave_shift": -2,
  "velocity": 100,
  "muted": false
}
```

**Note:** Track names in IR JSON are normalized to capitalized form (first letter uppercase) for puLang compatibility.

---

### Pattern

```python
@dataclass
class Pattern:
    pattern_type: str       # "arp", "root_eighths", "block_chords", etc.
    params: dict            # Pattern-specific parameters
```

**JSON:**
```json
{
  "type": "pattern",
  "pattern_type": "arp",
  "params": {
    "direction": "up",
    "rate": "1/16",
    "octaves": 1
  }
}
```

---

### Notes

Literal notes (the escape hatch).

```python
@dataclass
class Note:
    pitch: int              # MIDI pitch, or -1 for rest
    duration: str           # Fraction as string, e.g. "1/4"
    velocity: int | None    # Override, or None for track default
    offset: str             # Position within section (in beats), e.g. "0", "1/4"

@dataclass
class Notes:
    notes: list[Note]
```

**JSON:**
```json
{
  "type": "notes",
  "notes": [
    {"pitch": 60, "duration": "1/4", "velocity": null, "offset": "0"},
    {"pitch": 62, "duration": "1/4", "velocity": null, "offset": "1/4"},
    {"pitch": 64, "duration": "1/2", "velocity": null, "offset": "1/2"},
    {"pitch": -1, "duration": "1/4", "velocity": null, "offset": "1"},
    {"pitch": 67, "duration": "1/4", "velocity": 90, "offset": "5/4"}
  ]
}
```

---

### Fractions

Exact rational representation for durations and offsets.

Fractions are represented as **strings** in JSON: `"1/4"`, `"3/8"`, `"1"`.

In Python, we use `fractions.Fraction` from the standard library for exact arithmetic, and serialize to/from strings.

---

## Standard Dialect: Score IR

Module: `pulang.ir.score`

Score IR captures **realized musical content** — the specific pitches, rhythms, voices, articulations, and dynamics that result from lowering Intent IR. This is the level at which music theory analysis traditionally operates: you can see exactly which voice moves where, check for parallel fifths, analyze melodic contour, and evaluate counterpoint.

Score IR is **bar-relative and voice-aware**: pitches are named (not MIDI numbers), time is organized by bar and beat (not absolute position), and every note belongs to a named voice/part.

### Role of Score IR

Score IR is where the crucial musical decisions live that are invisible at both the Intent and Event levels:

```
Intent IR:  "I → IV → V → I in C major, 4 voices, block_chords pattern"
                           ↓ lowering (voice leading, voicing)
Score IR:   Soprano: E5  →  F5  →  D5  →  E5
            Alto:    C5  →  C5  →  B4  →  C5
            Tenor:   G4  →  A4  →  G4  →  G4
            Bass:    C3  →  F3  →  G3  →  C3
            (with dynamics: mf, articulation: legato)
                           ↓ lowering (performance interpretation)
Event IR:   {pitch: 64, start: "0", duration: "1", velocity: 80, track: "soprano"}
            {pitch: 65, start: "1", duration: "1", velocity: 80, track: "soprano"}
            ...
```

Score IR makes voice leading decisions, voicing choices, and expressive markings **inspectable, analyzable, and transformable** — rather than burying them inside a monolithic lowering function where they would be immediately discarded.

### Score

The top-level Score IR container. Represents a fully realized piece of music.

```python
@dataclass
class Score:
    title: str | None
    tempo: float                    # BPM
    key: Key                        # From intent module
    time_signature: TimeSignature   # From intent module
    parts: list[Part]
    sections: list[ScoreSection]    # Structural markers (for reference)
```

**JSON:**
```json
{
  "type": "score",
  "title": "Example",
  "tempo": 120,
  "key": {"root": "C", "mode": "major"},
  "time_signature": {"numerator": 4, "denominator": 4},
  "parts": [...],
  "sections": [...]
}
```

---

### Part

A named voice or instrument part. Unlike Intent IR tracks (which may contain patterns), parts contain fully realized notes.

```python
@dataclass
class Part:
    name: str
    role: str | None            # "melody", "bass", "harmony", "rhythm", or None
    instrument: str | int       # Name or MIDI program number
    bars: list[Bar]
```

**JSON:**
```json
{
  "type": "part",
  "name": "Soprano",
  "role": "melody",
  "instrument": "piano",
  "bars": [...]
}
```

---

### Bar

A single bar of music within a part. Contains notes organized by beat position.

```python
@dataclass
class Bar:
    number: int                     # 1-indexed bar number
    key: Key | None                 # Override (key change), or None to inherit
    time_signature: TimeSignature | None  # Override, or None to inherit
    notes: list[ScoreNote]
```

**JSON:**
```json
{
  "type": "bar",
  "number": 1,
  "key": null,
  "time_signature": null,
  "notes": [...]
}
```

---

### ScoreNote

A single note in Score IR. Uses scientific pitch notation, bar-relative timing, and carries articulation and dynamic information.

```python
@dataclass
class ScoreNote:
    pitch: str                  # Scientific notation: "C4", "F#5", "Bb3", or "rest"
    beat: str                   # Beat position within bar (fraction string), "1", "3/2"
    duration: str               # Duration in beats (fraction string), "1/4", "1"
    dynamic: str | None         # "pp", "p", "mp", "mf", "f", "ff", or None (inherit)
    articulation: str | None    # "staccato", "legato", "accent", "tenuto", etc.
    tie: str | None             # "start", "end", "continue", or None
    ornament: str | None        # "trill", "mordent", "turn", etc. (future)
    voice: int                  # Voice number within the part (for multi-voice parts)
```

**JSON:**
```json
{
  "type": "score_note",
  "pitch": "E5",
  "beat": "1",
  "duration": "1",
  "dynamic": "mf",
  "articulation": null,
  "tie": null,
  "ornament": null,
  "voice": 1
}
```

**Rest example:**
```json
{
  "type": "score_note",
  "pitch": "rest",
  "beat": "3",
  "duration": "1/2",
  "dynamic": null,
  "articulation": null,
  "tie": null,
  "ornament": null,
  "voice": 1
}
```

---

### ScoreSection

Structural markers in Score IR — these preserve the section boundaries from Intent IR for reference and analysis, but do not contain musical content (that lives in Parts/Bars).

```python
@dataclass
class ScoreSection:
    name: str
    start_bar: int      # 1-indexed
    end_bar: int        # Inclusive
```

**JSON:**
```json
{
  "type": "score_section",
  "name": "verse",
  "start_bar": 1,
  "end_bar": 8
}
```

---

### Dynamics and Articulation

Score IR uses standard musical terminology for dynamics and articulation:

**Dynamics** (from softest to loudest):
`"ppp"`, `"pp"`, `"p"`, `"mp"`, `"mf"`, `"f"`, `"ff"`, `"fff"`

Dynamic changes (applied to ranges of notes, future extension):
`"crescendo"`, `"decrescendo"`, `"sfz"`, `"fp"`

**Articulations:**
`"staccato"`, `"legato"`, `"accent"`, `"tenuto"`, `"marcato"`, `"portato"`

These map to concrete changes during Score → Event lowering (e.g., staccato shortens duration by ~50%, accent increases velocity by ~20%).

---

### Score IR Example

A four-bar I-IV-V-I chorale in C major:

```json
{
  "type": "score",
  "title": "Simple Chorale",
  "tempo": 72,
  "key": {"root": "C", "mode": "major"},
  "time_signature": {"numerator": 4, "denominator": 4},
  "sections": [
    {"type": "score_section", "name": "chorale", "start_bar": 1, "end_bar": 4}
  ],
  "parts": [
    {
      "type": "part",
      "name": "Soprano",
      "role": "melody",
      "instrument": "piano",
      "bars": [
        {
          "type": "bar", "number": 1, "key": null, "time_signature": null,
          "notes": [
            {"type": "score_note", "pitch": "E5", "beat": "1", "duration": "4", "dynamic": "mf", "articulation": null, "tie": null, "ornament": null, "voice": 1}
          ]
        },
        {
          "type": "bar", "number": 2, "key": null, "time_signature": null,
          "notes": [
            {"type": "score_note", "pitch": "F5", "beat": "1", "duration": "4", "dynamic": null, "articulation": null, "tie": null, "ornament": null, "voice": 1}
          ]
        },
        {
          "type": "bar", "number": 3, "key": null, "time_signature": null,
          "notes": [
            {"type": "score_note", "pitch": "D5", "beat": "1", "duration": "4", "dynamic": null, "articulation": null, "tie": null, "ornament": null, "voice": 1}
          ]
        },
        {
          "type": "bar", "number": 4, "key": null, "time_signature": null,
          "notes": [
            {"type": "score_note", "pitch": "E5", "beat": "1", "duration": "4", "dynamic": null, "articulation": null, "tie": null, "ornament": null, "voice": 1}
          ]
        }
      ]
    },
    {
      "type": "part",
      "name": "Bass",
      "role": "bass",
      "instrument": "piano",
      "bars": [
        {
          "type": "bar", "number": 1, "key": null, "time_signature": null,
          "notes": [
            {"type": "score_note", "pitch": "C3", "beat": "1", "duration": "4", "dynamic": "mf", "articulation": null, "tie": null, "ornament": null, "voice": 1}
          ]
        },
        {
          "type": "bar", "number": 2, "key": null, "time_signature": null,
          "notes": [
            {"type": "score_note", "pitch": "F3", "beat": "1", "duration": "4", "dynamic": null, "articulation": null, "tie": null, "ornament": null, "voice": 1}
          ]
        },
        {
          "type": "bar", "number": 3, "key": null, "time_signature": null,
          "notes": [
            {"type": "score_note", "pitch": "G3", "beat": "1", "duration": "4", "dynamic": null, "articulation": null, "tie": null, "ornament": null, "voice": 1}
          ]
        },
        {
          "type": "bar", "number": 4, "key": null, "time_signature": null,
          "notes": [
            {"type": "score_note", "pitch": "C3", "beat": "1", "duration": "4", "dynamic": null, "articulation": null, "tie": null, "ornament": null, "voice": 1}
          ]
        }
      ]
    }
  ]
}
```

---

## Standard Dialect: Event IR

Module: `pulang.ir.event`

The concrete, realized musical events. This is what backends consume. All musical abstraction has been resolved — pitches are MIDI numbers, times are absolute beat positions from the start of the piece, and there are no voices or bar structures, just a flat stream of events.

### EventStream

```python
@dataclass
class EventStream:
    tempo: float
    time_signature: TimeSignature
    events: list[Event]
```

**JSON:**
```json
{
  "type": "event_stream",
  "tempo": 120,
  "time_signature": {"numerator": 4, "denominator": 4},
  "events": [...]
}
```

---

### Event (Union Type)

```python
Event = NoteEvent | RestEvent | ControlEvent
```

---

### NoteEvent

```python
@dataclass
class NoteEvent:
    type: Literal["note"] = "note"
    pitch: int              # MIDI pitch (0-127)
    start: str              # Start time in beats from piece start (fraction string)
    duration: str           # Duration in beats (fraction string)
    velocity: int           # 0-127
    track: str              # Track name
```

**JSON:**
```json
{
  "type": "note",
  "pitch": 60,
  "start": "0",
  "duration": "1/4",
  "velocity": 100,
  "track": "piano"
}
```

---

### RestEvent

```python
@dataclass
class RestEvent:
    type: Literal["rest"] = "rest"
    start: str              # Fraction string
    duration: str           # Fraction string
    track: str
```

**JSON:**
```json
{
  "type": "rest",
  "start": "4",
  "duration": "1/4",
  "track": "melody"
}
```

---

### ControlEvent

For tempo changes, time signature changes, program changes, etc.

```python
@dataclass
class ControlEvent:
    type: Literal["control"] = "control"
    control_type: str       # "tempo", "time_signature", "program_change"
    value: Any              # Type depends on control_type
    time: str               # When it occurs (fraction string)
    track: str | None       # None for global controls
```

**JSON:**
```json
{
  "type": "control",
  "control_type": "tempo",
  "value": 140,
  "time": "32",
  "track": null
}
```

---

## Lowering: Intent IR → Score IR

The first lowering step converts compositional intent into realized musical content. This is where patterns become actual notes, Roman numerals become concrete pitches, and voice leading decisions are made.

### Algorithm Sketch

```python
from pulang.ir import intent, score

def lower_to_score(piece: intent.Piece, style: str = "default") -> score.Score:
    """Lower Intent IR to Score IR.

    The style parameter selects a lowering strategy:
    - "default": Basic voice leading with common-practice rules
    - "baroque": Figured bass realization conventions
    - "jazz": Jazz voicing and voice leading conventions
    - "romantic": Romantic-era part-writing conventions
    """
    parts_data = {}  # track_name -> list of bars
    current_bar = 1

    for section_name in piece.form or [s.name for s in piece.sections]:
        section = get_section(piece, section_name)
        key = section.key or piece.key
        time_sig = section.time_signature or piece.time_signature

        for track in section.tracks:
            if track.name not in parts_data:
                parts_data[track.name] = {"role": track.role, "instrument": track.instrument, "bars": []}

            if isinstance(track.content, intent.Pattern):
                bars = realize_pattern_to_bars(
                    track, section.harmony, key, time_sig,
                    start_bar=current_bar, style=style
                )
            elif isinstance(track.content, intent.Notes):
                bars = realize_notes_to_bars(
                    track, time_sig, start_bar=current_bar
                )
            parts_data[track.name]["bars"].extend(bars)

        current_bar += section.bars

    return score.Score(
        title=piece.title,
        tempo=piece.tempo,
        key=piece.key,
        time_signature=piece.time_signature,
        parts=[
            score.Part(name=name, role=data["role"],
                      instrument=data["instrument"], bars=data["bars"])
            for name, data in parts_data.items()
        ],
        sections=build_section_markers(piece)
    )
```

### Key Decisions in Intent → Score Lowering

| Decision | What it determines | Configurable via |
|----------|-------------------|-----------------|
| Chord voicing | Which octave, which inversion, open vs close | Voicing strategy / style |
| Voice leading | How voices move between chords | Voice leading rules |
| Pattern realization | How "arp up" becomes specific notes | Pattern generators |
| Register assignment | What octave each voice sings in | Track octave_shift + role defaults |
| Doubling | Which chord tones get doubled | Part-writing rules |
| Dynamics assignment | Default dynamic levels | Style defaults |

---

## Lowering: Score IR → Event IR

The second lowering step converts musical notation into performance events. This is where bar-relative timing becomes absolute timing, scientific pitch names become MIDI numbers, and articulation/dynamics become concrete velocity and duration adjustments.

### Algorithm Sketch

```python
from pulang.ir import score, event

def lower_to_events(s: score.Score) -> event.EventStream:
    """Lower Score IR to Event IR."""
    events = []
    beats_per_bar = Fraction(s.time_signature.numerator)

    for part in s.parts:
        for bar in part.bars:
            bar_offset = (bar.number - 1) * beats_per_bar
            ts = bar.time_signature or s.time_signature

            for note in bar.notes:
                if note.pitch == "rest":
                    events.append(event.RestEvent(
                        start=str(bar_offset + Fraction(note.beat)),
                        duration=note.duration,
                        track=part.name
                    ))
                else:
                    velocity = dynamic_to_velocity(note.dynamic or "mf")
                    duration = apply_articulation(note.duration, note.articulation)

                    events.append(event.NoteEvent(
                        pitch=pitch_to_midi(note.pitch),
                        start=str(bar_offset + Fraction(note.beat)),
                        duration=str(duration),
                        velocity=velocity,
                        track=part.name
                    ))

    return event.EventStream(
        tempo=s.tempo,
        time_signature=s.time_signature,
        events=sorted(events, key=lambda e: Fraction(e.start))
    )

def dynamic_to_velocity(dynamic: str) -> int:
    """Convert dynamic marking to MIDI velocity."""
    mapping = {
        "ppp": 16, "pp": 33, "p": 49, "mp": 64,
        "mf": 80, "f": 96, "ff": 112, "fff": 127
    }
    return mapping.get(dynamic, 80)

def apply_articulation(duration: str, articulation: str | None) -> Fraction:
    """Adjust duration based on articulation."""
    d = Fraction(duration)
    if articulation == "staccato":
        return d * Fraction(1, 2)
    elif articulation == "legato":
        return d  # Full value (or slightly overlap, configurable)
    elif articulation == "tenuto":
        return d  # Full held value
    return d * Fraction(9, 10)  # Default: slightly detached
```

### Key Decisions in Score → Event Lowering

| Decision | What it determines | Configurable via |
|----------|-------------------|-----------------|
| Dynamic → velocity mapping | How loud "forte" is | Velocity curve |
| Articulation → duration | How short "staccato" is | Articulation table |
| Pitch → MIDI | Enharmonic resolution | Pitch mapping |
| Bar position → absolute time | Rubato, tempo changes | Tempo map |

---

## Serialization Format

All IR uses JSON with the following conventions:

1. **Type discriminator** — Every object has a `"type"` field
2. **Fractions as strings** — `"1/4"`, `"3/8"`, `"1"` (whole number)
3. **Null for optional** — Missing optional fields are `null`
4. **Lists for sequences** — Arrays, not objects with numeric keys
5. **Dialect marker** — Top-level objects include `"dialect"` field: `"intent"`, `"score"`, or `"event"`

### Example: Complete Intent IR Piece

```json
{
  "dialect": "intent",
  "type": "piece",
  "title": "Example Composition",
  "tempo": 120,
  "key": {"root": "G", "mode": "major"},
  "time_signature": {"numerator": 4, "denominator": 4},
  "form": ["intro", "verse", "chorus"],
  "sections": [
    {
      "type": "section",
      "name": "intro",
      "bars": 4,
      "key": null,
      "time_signature": null,
      "harmony": {
        "type": "harmony",
        "duration_unit": "bars",
        "changes": [
          {"chord": {"numeral": "I", "quality": "major", "extensions": [], "inversion": 0, "secondary": null}, "duration": "2"},
          {"chord": {"numeral": "IV", "quality": "major", "extensions": [], "inversion": 0, "secondary": null}, "duration": "2"}
        ]
      },
      "tracks": [
        {
          "type": "track",
          "name": "Keys",
          "role": "harmony",
          "instrument": "piano",
          "content": {
            "type": "pattern",
            "pattern_type": "arp",
            "params": {"direction": "up", "rate": "1/16"}
          },
          "octave_shift": 0,
          "velocity": 80,
          "muted": false
        }
      ]
    }
  ]
}
```

---

## Validation Rules

### Intent IR Validation

1. **Key validity** — Root must be valid pitch class, mode must be recognized
2. **Time signature** — Denominator must be power of 2
3. **Harmony duration** — Must sum to section length
4. **Roman numerals** — Must be I-VII (or i-vii)
5. **Form references** — All section names must exist

### Score IR Validation

1. **Pitch names** — Must be valid scientific notation (e.g., "C4", "F#5") or "rest"
2. **Beat positions** — Must be within bar bounds (>= 1, <= bar length in beats)
3. **Dynamics** — Must be recognized dynamic marking
4. **Articulations** — Must be recognized articulation
5. **Voice consistency** — Voice numbers should be consistent within a part
6. **Bar numbering** — Bars should be sequential and contiguous

### Event IR Validation

1. **Pitch range** — 0-127 for MIDI
2. **Velocity range** — 0-127
3. **Non-negative times** — start >= 0, duration > 0
4. **Chronological** — Events should be sorted by start time

---

## Extension Points

### Custom Pattern Types

New patterns can be registered:

```python
PATTERN_REGISTRY["my_pattern"] = my_pattern_generator
```

The IR just stores the pattern type name; the generator is looked up at realization time.

### Custom Control Events

The `control_type` field is open-ended:
- Standard: `"tempo"`, `"time_signature"`, `"program_change"`
- Extended: `"expression"`, `"modulation"`, custom types

### Custom Passes

Passes can be defined and registered for any dialect:

```python
@analysis_pass(dialect="score")
def parallel_fifths_check(score: Score) -> AnalysisResult:
    """Check for parallel fifths between all voice pairs."""
    ...

@transform_pass(dialect="intent")
def tritone_substitution(piece: Piece) -> Piece:
    """Replace dominant chords with tritone substitutions."""
    ...
```

### Custom Dialects

New dialects can be defined by specifying:
1. A set of operation types (dataclasses)
2. A type system (pitch representation, timing representation, etc.)
3. Lowering/lifting rules to connect to existing dialects

```python
@dialect("schenkerian")
class SchenkerianDialect:
    """Schenkerian analysis dialect."""
    operations = [Ursatz, Prolongation, StructuralLevel, ...]
    types = [ScaleDegree, StructuralWeight, ...]
    lifts_from = ["score"]  # Can be produced by analyzing Score IR
```

### Metadata

All IR levels can carry arbitrary metadata:

```python
@dataclass
class Piece:
    # ... standard fields ...
    metadata: dict | None   # Arbitrary key-value pairs
```

---

## Analytical Dialect Examples

These dialects are not part of puLang's standard distribution but illustrate the framework's extensibility. They represent real musicological analysis methods that could be formalized as IR dialects.

### Schenkerian Dialect

Schenkerian analysis represents music as hierarchical structural levels, revealing the deep structure beneath surface elaboration.

```
score.* ──lifting──→ schenkerian.*

Score IR (foreground):   C4 D4 E4 F4 | E4 D4 C4 ...
  → middleground:       C4 ---- E4 -- | E4 ---- C4 ...  (passing tones removed)
  → background:         C4 ---------- | ---------- C4    (Ursatz: scale degree 1)
```

A Schenkerian dialect would define operations for structural levels, prolongation types (neighbor, passing, arpeggiation), and Ursätze. Lifting from Score IR would involve algorithmically identifying structural tones — a non-trivial analytical task with multiple valid interpretations.

### Set Theory Dialect

Pitch class set theory analyzes music in terms of unordered collections of pitch classes, independent of octave and order.

```
score.* ──lifting──→ settheory.*

Score IR:   [C4, E4, G4]  →  [C5, Eb5, G5]  →  [C4, E4, G#4]
  → PCS:   {0, 4, 7} [3-11]  →  {0, 3, 7} [3-11]  →  {0, 4, 8} [3-12]
  → IC vector: <001110> → <001110> → <000300>
```

Useful for analyzing post-tonal music where Roman numeral analysis doesn't apply. A set theory dialect would define operations for set classes, interval vectors, and transformational networks (transposition, inversion, multiplication).

### Counterpoint Dialect

Species counterpoint analysis evaluates voice pairs against the rules of strict counterpoint.

```
score.* ──lifting──→ counterpoint.*

Score IR (two voices): Soprano + Bass
  → Species: First species (note-against-note)
  → Intervals: P5, m3, M6, P8, M3, ...
  → Errors: parallel fifth at bar 7, direct octave at bar 12
```

A counterpoint dialect would define operations for species classification, interval sequences, motion types (parallel, contrary, oblique, similar), and rule violations.

---

## Style Dialects

Style dialects capture idiom-specific conventions that affect how Intent IR is lowered to Score IR.

### Jazz Dialect

Jazz conventions include specific voicing types, comping rhythms, and walking bass idioms that don't exist in common-practice harmony.

A jazz dialect might define:
- **Voicing types**: Shell voicings (3rd + 7th), drop-2, rootless, quartal
- **Comping rhythms**: Charleston, Freddie Green, bossa nova
- **Walking bass idioms**: Approach patterns, chromatic enclosures
- **Lead sheet ops**: Chord symbols, melody + changes format

When jazz dialect is active, Intent → Score lowering would use jazz-specific voice leading rules (e.g., guide tone lines, tritone substitution voicings) rather than common-practice rules.

### Baroque Dialect

Baroque conventions include figured bass realization, ornament tables, and continuo practices.

A baroque dialect might define:
- **Figured bass ops**: Bass note + figures → chord realization
- **Ornament types**: Trill (from above), mordent, appoggiatura, turns — with style-period-specific realization rules
- **Continuo rules**: Standard realization patterns for common bass figures

---

## Design Decisions to Resolve

These are open questions for the dialect framework that need further design work:

### 1. Dialect Definition API

How exactly do users define new dialects? Options:
- **Declarative**: Define operations and types as dataclasses, register with decorator
- **Programmatic**: Implement a `Dialect` protocol with `operations()`, `types()`, `validate()`
- **Hybrid**: Dataclass definitions + protocol for lowering/lifting

### 2. Pass Composition and Ordering

How do passes compose? Options:
- **Explicit pipeline**: User specifies exact order: `pipe(pass1, pass2, pass3)`
- **Dependency-based**: Passes declare what they need, framework topologically sorts
- **Constraint-based**: Passes declare ordering constraints ("must run before X")

### 3. Lifting Ambiguity

Lifting is inherently ambiguous (multiple valid analyses). How to handle:
- **Single result**: Return best-guess analysis (simplest, most common)
- **Multiple results**: Return ranked list of candidate analyses
- **Configurable**: User selects analytical framework/preferences

### 4. Score IR Granularity

How much detail should Score IR carry? Current design is moderate:
- **Minimal**: Just pitches, durations, voices — articulation and dynamics stay in a separate layer
- **Moderate** (current): Pitches, durations, voices, dynamics, articulation
- **Maximal**: Add beaming, stem direction, slurs, pedal markings, fingering, etc.

The current choice is moderate — enough for musical analysis and MusicXML export, not so much that it becomes a notation format. Engraving details are out of scope (use LilyPond/Dorico for that).

### 5. Direct Intent → Event Path

Should users be able to skip Score IR and go Intent → Event directly?
- **Keep direct path**: Intent → Event lowering works as a convenience (internally goes through Score IR)
- **Explicit only**: Require explicit two-step lowering (Intent → Score → Event)
- **Both** (current plan): Direct path works but is syntactic sugar for Intent → Score → Event

---

## Future Considerations

### Music IR Compatibility

When evolving toward a shared Music IR ecosystem:

1. **Namespace** — `music_ir.intent.*`, `music_ir.score.*`, `music_ir.event.*`
2. **Versioning** — Add `"version": "0.2"` to root objects
3. **Schema** — Publish JSON Schema for validation
4. **Dialect registry** — Community-maintained dialect definitions
5. **Interop** — Import/export to/from music21, MusicXML, MEI, Humdrum

### Additional Standard Dialects

Potential future standard dialects beyond Intent/Score/Event:
- **Audio IR** — Sample references, synthesis parameters, mixing instructions
- **Notation IR** — Beaming, layout, engraving hints (if we decide to go there)
- **Performance IR** — Detailed performance instructions beyond what Event IR captures (breath marks, bowing, pedaling)

### Pass Ecosystem

A rich ecosystem of reusable passes is one of the most valuable things puLang could provide to the music technology community. Imagine:
- `pip install pulang-schenkerian` — Schenkerian analysis passes
- `pip install pulang-jazz-voicings` — Jazz-specific lowering strategies
- `pip install pulang-baroque-ornaments` — Baroque ornament realization
- `pip install pulang-voice-leading` — Advanced voice leading optimization

Each package would register its dialects and passes with the framework.
