# puLang IR Specification

*Draft v0.1 — Minimal viable IR*

---

## Overview

puLang uses a two-tier IR architecture:

1. **Intent IR** — Captures compositional intent (harmony, patterns, structure)
2. **Event IR** — Captures concrete musical events (notes, rests, timings)

### Two Syntaxes, One IR

puLang has two distinct frontend syntaxes that both emit identical Intent IR:

| Syntax | Description | File Type | Target Users |
|--------|-------------|-----------|--------------|
| **pyPuLang** | Python-embedded DSL with context managers and method chaining | `.py` | Programmers, AI/ML researchers |
| **puLang** | Standalone music-native syntax, inspired by sheet music | `.pu` | Musicians, composers |

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
            │   Intent IR   │
            │  (JSON file)  │
            └───────┬───────┘
                    ▼
            ┌───────────────┐
            │  Transforms   │
            └───────┬───────┘
                    ▼
            ┌───────────────┐
            │   Event IR    │
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
| Intent IR | Bar-relative | `{"bar": 2, "beat": "3/2"}` | Matches musical thinking |
| Event IR | Piece-relative | `{"start": "13/2"}` | Simple math for backends |

### Pitch Representation

| IR Layer | Representation | Example | Rationale |
|----------|----------------|---------|-----------|
| Intent IR | Scientific notation | `"C#4"` | Human-readable, preserves enharmonic |
| Event IR | MIDI integer | `61` | Direct backend mapping |

---

## Intent IR

Module: `pulang.ir.intent`

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

## Event IR

Module: `pulang.ir.event`

The concrete, realized musical events. This is what backends consume.

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

## Realization: Intent IR → Event IR

The realization process converts Intent IR to Event IR.

### Algorithm Sketch

```python
from pulang.ir import intent, event

def realize(piece: intent.Piece) -> event.EventStream:
    events = []
    current_beat = Fraction(0)

    for section_name in piece.form or [s.name for s in piece.sections]:
        section = get_section(piece, section_name)
        section_events = realize_section(section, piece, current_beat)
        events.extend(section_events)
        current_beat += section_length_in_beats(section, piece.time_signature)

    return event.EventStream(
        tempo=piece.tempo,
        time_signature=piece.time_signature,
        events=sorted(events, key=lambda e: e.start)
    )

def realize_section(section: intent.Section, piece: intent.Piece,
                    offset: Fraction) -> list[event.Event]:
    events = []
    key = section.key or piece.key
    time_sig = section.time_signature or piece.time_signature

    for track in section.tracks:
        if isinstance(track.content, intent.Pattern):
            events.extend(realize_pattern(track, section.harmony, key, time_sig, offset))
        elif isinstance(track.content, intent.Notes):
            events.extend(realize_notes(track, offset))

    return events

def realize_pattern(track: intent.Track, harmony: intent.Harmony, key: intent.Key,
                    time_sig: intent.TimeSignature, offset: Fraction) -> list[event.NoteEvent]:
    # Get pattern generator
    generator = PATTERN_REGISTRY[track.content.pattern_type]

    # Generate events for each chord in the progression
    events = []
    chord_offset = offset
    for change in harmony.changes:
        chord_pitches = resolve_chord(change.chord, key)
        chord_duration = to_beats(change.duration, harmony.duration_unit, time_sig)
        pattern_events = generator(
            chord_pitches=chord_pitches,
            duration=chord_duration,
            offset=chord_offset,
            track=track,
            params=track.content.params
        )
        events.extend(pattern_events)
        chord_offset += chord_duration

    return events
```

---

## Serialization Format

All IR uses JSON with the following conventions:

1. **Type discriminator** — Every object has a `"type"` field
2. **Fractions as strings** — `"1/4"`, `"3/8"`, `"1"` (whole number)
3. **Null for optional** — Missing optional fields are `null`
4. **Lists for sequences** — Arrays, not objects with numeric keys

### Example: Complete Piece

```json
{
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
          "name": "keys",
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

### Metadata

Both IR levels can carry arbitrary metadata:

```python
@dataclass
class Piece:
    # ... standard fields ...
    metadata: dict | None   # Arbitrary key-value pairs
```

---

## Future Considerations

### Music IR Compatibility

When evolving toward a shared Music IR:

1. **Namespace** — Intent IR becomes `music_ir.intent.*`
2. **Versioning** — Add `"version": "0.1"` to root objects
3. **Schema** — Publish JSON Schema for validation
4. **Dialects** — Intent IR and Event IR become named dialects

### Additional IR Levels

Potential future dialects:
- **Notation IR** — Beaming, layout, engraving hints
- **Performance IR** — Articulation, dynamics, expression
- **Audio IR** — Sample references, synthesis parameters

These are out of scope for v0.1.
