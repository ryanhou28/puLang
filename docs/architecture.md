# puLang Architecture

## Overview

puLang uses a **compiler-style architecture** with clear separation between:
- **Frontends** — pyPuLang (Python DSL) and puLang (standalone syntax)
- **IR (Intermediate Representation)** — a three-tier dialect system for representing music at different levels of abstraction
- **Passes** — analysis and transformation at each IR level
- **Backends** — emitters to MIDI, MusicXML, audio, etc.

The architecture is built on a **dialect framework** inspired by MLIR: rather than hardcoding fixed IR levels, puLang provides infrastructure for defining dialects, passes, and lowering/lifting rules. The three standard dialects — Intent, Score, and Event — are shipped with puLang, but the framework supports user-defined dialects for specialized analysis or style-specific conventions.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontends                                │
├────────────────────────────────┬────────────────────────────────┤
│         pyPuLang (Python)      │      puLang (Standalone)       │
│  piece() → section() → ...     │   piece "X": section ...       │
└────────────────────────────────┴────────────────────────────────┘
                              │
                              ▼ lowering
┌─────────────────────────────────────────────────────────────────┐
│                         Intent IR                                │
│   Sections, Harmony (Roman numerals), Patterns, Tracks, Roles   │
│   ← intent-level passes: harmonic analysis, form detection,     │
│     reharmonization, transposition, modulation                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ lowering (voicing, voice leading, pattern realization)
┌─────────────────────────────────────────────────────────────────┐
│                         Score IR                                 │
│   Parts, Bars, Named pitches, Voices, Dynamics, Articulation    │
│   ← score-level passes: voice leading analysis, counterpoint,   │
│     melodic contour, texture analysis, ornamentation            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ lowering (performance interpretation)
┌─────────────────────────────────────────────────────────────────┐
│                          Event IR                                │
│   Concrete MIDI-like events, absolute timing, velocities        │
│   ← event-level passes: humanize, quantize, swing, groove       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ emission
┌─────────────────────────────────────────────────────────────────┐
│                          Backends                                │
│   MIDI  │  MusicXML  │  Audio  │  JSON  │  LilyPond  │  ...    │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Dialect Framework

The architecture's core innovation is treating IR levels as **dialects** within a common framework, rather than ad-hoc data structures. This design is inspired by MLIR (Multi-Level Intermediate Representation) from the compiler world.

### What is a Dialect?

A dialect is a named collection of:
- **Operations** — the data types that represent musical things (notes, chords, sections, events)
- **Types** — how fundamental musical concepts are represented (pitches, durations, intervals)
- **Passes** — analysis and transformation functions that operate on this dialect
- **Lowering rules** — how to convert from this dialect to a lower-level one
- **Lifting rules** — how to convert from a lower-level dialect to this one (analysis)

### Standard Dialects

puLang ships three standard dialects:

| Dialect | Module | Captures | Pitch | Timing |
|---------|--------|----------|-------|--------|
| **Intent** | `pulang.ir.intent` | Compositional intent | Roman numerals | Bar counts |
| **Score** | `pulang.ir.score` | Realized musical content | Scientific notation ("C#4") | Bar-relative beats |
| **Event** | `pulang.ir.event` | Performance events | MIDI integers (0-127) | Piece-relative beats |

### Why Three Levels?

Each level captures music at a different level of abstraction, matching how different people think about music:

- **Intent** = how a **composer plans**: "I want a I-IV-V-I progression with arpeggiated piano"
- **Score** = how a **music theorist analyzes**: "The soprano moves E5→F5→D5→E5 with stepwise motion"
- **Event** = how a **performer/machine executes**: "Play MIDI note 64 at beat 0 for 1 beat at velocity 80"

The gap between Intent and Event was too large. Score IR fills this gap by making voice leading decisions, voicing choices, and expressive markings **explicit, inspectable, and transformable** — rather than burying them inside a monolithic lowering function.

### Extensible Dialects

The framework supports user-defined dialects for specialized purposes:

- **Analytical dialects**: Schenkerian analysis, set theory, counterpoint species
- **Style dialects**: Jazz voicings, Baroque ornaments, Romantic expression
- **Domain dialects**: Film scoring, game audio, educational exercises

See [ir-spec.md](ir-spec.md) for detailed dialect specifications and examples.

---

## Layer 1: Frontends

puLang has two frontends that emit identical Intent IR.

### pyPuLang (Python-embedded DSL)

Python-embedded DSL using context managers and method chaining. Pythonic, readable, notebook-friendly.

```python
from pypulang import *

with piece(tempo=120, key="D major", time_sig="4/4") as p:

    verse = p.section("verse", bars=8)
    verse.harmony(I, IV, vi, V)
    verse.track("bass").pattern(root_eighths).octave(-2)
    verse.track("keys").pattern(arp("up"), rate=1/16)
    verse.track("melody").notes([...])  # escape hatch

    chorus = verse.transform(
        reharmonize="modal_interchange",
        density=1.2
    )
    chorus.name = "chorus"

p.save_midi("output.mid")
```

### puLang (Standalone Syntax — Future)

Music-native syntax designed for accessibility to non-programmers.

```
piece "My Song" tempo=120 key=D time=4/4:

  Verse [8 bars]:
    harmony: I  IV  vi  V

    Bass:
      pattern: root_eighths
      octave: -2

    Keys:
      pattern: arp up
      rate: 1/16

    Melody:
      notes: [...]

  Chorus = Verse.transform:
    reharmonize: modal_interchange
    density: 1.2
```

**Note:** The standalone syntax is co-designed with pyPuLang but implemented later. Both syntaxes have identical semantics.

### Frontend Responsibilities
- Provide ergonomic syntax for composers
- Validate input (key signatures, time signatures, etc.)
- Lower to Intent IR

### Frontends Do NOT
- Know about MIDI
- Know about audio
- Perform transforms (just invoke them)

---

## Layer 2: Intent IR

### Design Principle
Represents **what** the composer wants, not **how** it sounds. Captures harmonic, structural, and pattern-level intent.

### Core Types

```python
@dataclass
class PieceIR:
    tempo: float
    key: Key
    time_signature: TimeSignature
    sections: list[SectionIR]

@dataclass
class SectionIR:
    name: str
    bars: int
    harmony: HarmonyIR
    tracks: list[TrackIR]

@dataclass
class HarmonyIR:
    """Chord progression as roman numerals + durations."""
    changes: list[tuple[RomanNumeral, Duration]]

@dataclass
class TrackIR:
    name: str
    role: Role  # melody, bass, harmony, rhythm, etc.
    content: PatternIR | NotesIR

@dataclass
class PatternIR:
    """A generator that produces notes from harmony."""
    pattern_type: str  # "arp", "root_eighths", "block_chord", etc.
    params: dict

@dataclass
class NotesIR:
    """Literal notes (escape hatch)."""
    notes: list[NoteIR]
```

### Key Design Decisions

1. **Roman numerals, not absolute chords** — Allows transposition, modal interchange
2. **Patterns, not notes** — Defer voicing decisions to realization
3. **Roles, not just names** — "bass" vs "melody" affects voice leading
4. **Serializable** — Can be saved as JSON, shared, versioned

### Intent-Level Passes

**Analysis passes** operate on Intent IR to understand compositional structure:
- Harmonic function analysis (tonic, predominant, dominant classification)
- Form analysis (binary, ternary, sonata, rondo, verse-chorus detection)
- Harmonic rhythm analysis (chord change rate relative to meter)
- Modulation detection (key center shifts, pivot chords)

**Transform passes** modify Intent IR:
- Reharmonization (modal interchange, tritone substitution, secondary dominants)
- Transposition (shift key center)
- Modulation (introduce key change with pivot chord)
- Restructure (reorder, duplicate, or remove sections)

---

## Layer 3: Score IR

### Design Principle
Represents **realized musical content** — the specific pitches, voices, articulations, and dynamics that result from lowering Intent IR. This is where music theory analysis traditionally operates.

### Core Types

```python
@dataclass
class Score:
    title: str | None
    tempo: float
    key: Key
    time_signature: TimeSignature
    parts: list[Part]
    sections: list[ScoreSection]

@dataclass
class Part:
    name: str
    role: str | None
    instrument: str | int
    bars: list[Bar]

@dataclass
class Bar:
    number: int
    key: Key | None
    time_signature: TimeSignature | None
    notes: list[ScoreNote]

@dataclass
class ScoreNote:
    pitch: str              # "C4", "F#5", "rest"
    beat: str               # Bar-relative beat position
    duration: str           # Duration in beats
    dynamic: str | None     # "pp" through "fff"
    articulation: str | None  # "staccato", "legato", etc.
    tie: str | None         # "start", "end", "continue"
    voice: int              # Voice number within part
```

### Key Design Decisions

1. **Named pitches, not MIDI numbers** — Preserves enharmonic spelling, human-readable
2. **Bar-relative timing** — Matches how musicians think ("beat 3 of bar 2")
3. **Explicit voices** — Every note belongs to a voice, enabling counterpoint analysis
4. **Dynamics and articulation** — Expressive markings preserved for analysis and Score → Event lowering
5. **Moderate granularity** — Enough for theory analysis and MusicXML export; not a notation format (no beaming, stem direction, layout)

### Score-Level Passes

**Analysis passes** — the heart of music theory analysis:
- Voice leading analysis (parallel fifths/octaves, tendency tone resolution, voice crossing)
- Counterpoint analysis (species identification, voice independence, dissonance treatment)
- Melodic contour analysis (shape classification, interval content)
- Texture analysis (homophonic, polyphonic, monophonic, homorhythmic; density)
- Range analysis (per-voice, against standard SATB/instrument ranges)
- Register analysis (voice spacing, registral gaps)

**Transform passes**:
- Voice leading optimization (minimize movement, resolve tendency tones, avoid parallels)
- Add ornamentation (passing tones, neighbor tones, suspensions, anticipations)
- Apply articulation (staccato, legato, accents based on style rules)
- Adjust dynamics (dynamic curves, phrasing dynamics)
- Change voicing (close, open, drop-2, spread)
- Orchestrate (assign voices to instruments with idiomatic adjustments)

### Lowering: Intent → Score

This is where the critical musical decisions happen:
- **Chord voicing**: Which octave, which inversion, open vs close position
- **Voice leading**: How voices move between chords
- **Pattern realization**: How "arp up" becomes specific notes in specific voices
- **Style conventions**: Baroque continuo realization vs jazz voicings vs Romantic part-writing

The lowering process is **configurable by style** — different styles encode different musicological conventions. This makes the lowering itself a musicological statement that can be inspected, debated, and swapped.

---

## Layer 4: Event IR

### Design Principle
Represents **concrete musical events** — the actual notes to be played. This is the "object code" of puLang.

### Core Types

```python
@dataclass
class EventIR:
    events: list[NoteEvent | RestEvent | ControlEvent]
    tempo: float
    time_signature: TimeSignature

@dataclass
class NoteEvent:
    pitch: int          # MIDI pitch (0-127)
    start: Fraction     # Start time in beats
    duration: Fraction  # Duration in beats
    velocity: int       # 0-127
    track: str          # Track name

@dataclass
class RestEvent:
    start: Fraction
    duration: Fraction
    track: str

@dataclass
class ControlEvent:
    type: str           # "tempo", "time_sig", "program_change", etc.
    value: Any
    time: Fraction
```

### Event-Level Passes

**Analysis passes**:
- Groove analysis (timing deviations, swing ratio)
- Dynamics analysis (velocity curves, dynamic range)
- Articulation detection (staccato vs legato from note overlap)
- Density analysis (notes per beat over time)

**Transform passes**:
- Humanize (add timing/velocity variation)
- Quantize (snap to rhythmic grid)
- Apply swing (offset alternating subdivisions)
- Compress dynamics (narrow/expand velocity range)
- Time-stretch (scale all timings)

### Lowering: Score → Event

This is where notation becomes performance:
- **Dynamic → velocity**: "forte" becomes velocity 96
- **Articulation → duration**: "staccato" shortens to ~50%
- **Named pitch → MIDI**: "C#4" becomes 61
- **Bar-relative → absolute**: Bar 3, beat 2 becomes beat 10

### Design Decisions

1. **Fractional timing** — Use `fractions.Fraction` for exact beat positions
2. **Track names preserved** — For multi-track MIDI export
3. **No MIDI-specific data** — Event IR is format-agnostic
4. **Sorted by time** — Events are in chronological order

---

## Layer 5: Backends

### Design Principle
Backends are **stateless emitters** that convert Event IR to output formats.

### MIDI Backend (Primary)
```python
def emit_midi(events: EventIR, path: str) -> None:
    """Write to Standard MIDI File."""
    # Use mido or similar library
```

### MusicXML Backend
```python
def emit_musicxml(score: Score, path: str) -> None:
    """Write to MusicXML for notation software.

    Note: MusicXML export works best from Score IR (not Event IR)
    since Score IR preserves bar structure, voices, and articulations.
    """
```

### JSON Backend
```python
def emit_json(ir: Piece | Score | EventIR, path: str) -> None:
    """Serialize IR for debugging/interchange.

    Can serialize any dialect level.
    """
```

### Audio Backend (Future)
```python
def emit_audio(events: EventIR, path: str, soundfont: str) -> None:
    """Render to audio using FluidSynth or similar."""
```

---

## Passes Architecture

Passes are first-class citizens in puLang's architecture. They are the primary mechanism for both analysis and transformation of music.

### Pass Categories

| Category | Input | Output | Purpose |
|----------|-------|--------|---------|
| **Analysis** | IR (any dialect) | Analysis results | Understand musical structure |
| **Transform** | IR (any dialect) | New IR (same dialect) | Modify musical content |
| **Lowering** | IR (higher dialect) | IR (lower dialect) | Compile toward performance |
| **Lifting** | IR (lower dialect) | IR (higher dialect) | Analyze / reverse-engineer |

### Pass Design Principles

1. **Pure functions** — Passes take IR and return results/new IR. No mutation.
2. **Composable** — Passes can be chained into pipelines.
3. **Dialect-aware** — Each pass declares which dialect(s) it operates on.
4. **Configurable** — Passes accept parameters for different strategies.
5. **Registerable** — Custom passes can be added to the framework.

### Lowering as Musicological Statement

The lowering process between dialects is not mechanical — it encodes deep musicological knowledge:

**Intent → Score lowering** encodes voice leading pedagogy, voicing conventions, and style-period norms. A Baroque continuo realization is fundamentally different from a jazz comping pattern, even for the same chord progression. By making lowering configurable by style, puLang makes these decisions **explicit and debatable**.

**Score → Event lowering** encodes performance practice. How long is "staccato"? What velocity is "forte"? How should rubato feel? These are interpretive decisions that vary by performer, era, and tradition.

### Lifting as Analysis

Passes can go **up** as well as down — this is what musicologists do:

- **Event → Score** (transcription): Infer notation from a MIDI performance
- **Score → Intent** (harmonic analysis): Infer Roman numerals from specific pitches
- **Score → analytical dialect**: Schenkerian reduction, set-theoretic analysis, etc.

Lifting is inherently interpretive. Multiple valid analyses may exist. The framework supports this by allowing multiple lifting strategies and ranked results.

---

## Transform Pipeline

### Design Principle
Transforms are **pure functions** that take IR and return IR. They can be composed and ordered.

### Transform Types

#### Harmonic Transforms (Intent-level)
```python
def reharmonize(ir: SectionIR, strategy: str) -> SectionIR:
    """Replace chords using substitution strategies."""
    # modal_interchange, tritone_sub, secondary_dominant, etc.

def transpose(ir: PieceIR, interval: int) -> PieceIR:
    """Transpose entire piece."""

def modulate(ir: SectionIR, to_key: Key, pivot: RomanNumeral) -> SectionIR:
    """Introduce modulation."""
```

#### Voice Transforms (Score-level)
```python
def voice_lead(score: Score, max_leap: int = 4) -> Score:
    """Optimize voice leading across chord changes."""

def add_ornaments(score: Score, style: str = "baroque") -> Score:
    """Insert passing tones, neighbor tones, suspensions."""

def change_voicing(score: Score, voicing: str = "open") -> Score:
    """Switch between close, open, drop-2, spread voicings."""
```

#### Textural Transforms (Score-level)
```python
def thin_texture(score: Score, except_roles: list[Role]) -> Score:
    """Reduce density by removing notes."""

def thicken_texture(score: Score, strategy: str) -> Score:
    """Add doublings, fill voicings."""

def change_register(score: Score, octaves: int) -> Score:
    """Shift up/down."""
```

#### Performance Transforms (Event-level)
```python
def humanize(events: EventIR, amount: float = 0.1) -> EventIR:
    """Add subtle timing/velocity variation."""

def apply_swing(events: EventIR, ratio: float = 0.67) -> EventIR:
    """Offset alternating subdivisions."""
```

### Transform Ordering

Transforms may have dependencies:
1. Harmonic transforms first (change the chords) — Intent level
2. Lowering to Score (realize voicings)
3. Voice leading transforms (optimize movement) — Score level
4. Textural transforms (adjust density) — Score level
5. Lowering to Event (performance interpretation)
6. Performance transforms (humanize, swing) — Event level

The pipeline should either:
- Enforce ordering constraints
- Or let the user specify order explicitly

**Phase 1:** Explicit user ordering. Implicit ordering is a future enhancement.

---

## Playback Architecture

For rapid iteration, playback latency is critical. pypulang uses a **protocol-based backend system** that allows multiple playback methods while keeping the user API simple.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      User API                                    │
│  p.play()  p.loop()  p.stop()  p.pause()  p.resume()           │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                 PlaybackBackend Protocol                         │
│  play(events, instruments) → PlaybackHandle                     │
│  is_available() → bool                                          │
│  name() → str                                                   │
└─────────────────┬───────────────────────────────────────────────┘
                  │
      ┌───────────┼───────────────────┐
      ▼           ▼                   ▼
┌───────────┐ ┌───────────┐   ┌─────────────────┐
│BuiltinSynth│ │VirtualMidi│   │ FluidSynth     │
│ (Default)  │ │  → DAW    │   │ (Future)       │
└───────────┘ └───────────┘   └─────────────────┘
```

### PlaybackBackend Protocol

All playback backends implement this protocol:

```python
class PlaybackBackend(Protocol):
    """Protocol for all playback backends."""

    def play(self, events: EventStream, instruments: InstrumentBank) -> PlaybackHandle:
        """Start playback, return handle for transport control."""
        ...

    def is_available(self) -> bool:
        """Check if this backend can be used (dependencies installed, etc.)."""
        ...

    def name(self) -> str:
        """Human-readable backend name."""
        ...

class PlaybackHandle(Protocol):
    """Handle for controlling active playback."""

    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def is_playing(self) -> bool: ...
```

### Backend Selection

```python
import pypulang

# Global default (built-in synth if available)
p.play()

# Set global default
pypulang.set_default_backend(VirtualMidi("pypulang"))
p.play()  # Now uses virtual MIDI

# Per-call override
p.play(backend=BuiltinSynth())
```

### Built-in Synth Backend (Default)

The default backend uses waveform synthesis with `sounddevice` for audio output.

**Dependencies:** `sounddevice`, `numpy` (optional install: `pypulang[playback]`)

**Features:**
- Waveform synthesis: sine, square, saw, triangle
- ADSR envelope generator
- Basic filters (lowpass, highpass)
- Real-time mixing of multiple tracks
- Target latency: <50ms

### Virtual MIDI Backend (DAW Integration)

Routes MIDI events to external synthesizers via virtual MIDI ports.

**Dependencies:** `python-rtmidi` (optional install: `pypulang[midi]`)

**Features:**
- Create virtual MIDI ports
- Route to DAWs (Ableton, Logic, etc.)
- Use professional instruments and effects
- Low latency real-time output

```python
p.connect(port="pypulang")  # Create virtual port
p.play(backend=VirtualMidi("pypulang"))
```

### FluidSynth Backend (Future)

High-quality SoundFont-based synthesis.

**Dependencies:** `pyfluidsynth` (optional install: `pypulang[fluidsynth]`)

**Target latency:** <100ms from `play()` to sound (all backends).

---

## Instrument System

The instrument system provides configurable sound sources for the built-in synth backend.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Instrument (ABC)                              │
│  render(note: NoteEvent, sample_rate: int) -> np.ndarray        │
└─────────────────┬───────────────────────────────────────────────┘
                  │
      ┌───────────┼───────────────────┐
      ▼           ▼                   ▼
┌───────────┐ ┌─────────────────┐ ┌───────────┐
│   Synth   │ │SampledInstrument│ │  Sampler  │
│ (Phase 2) │ │    (Future)     │ │ (Future)  │
│           │ │                 │ │           │
│ Waveform  │ │ Bundled samples │ │ User      │
│ synthesis │ │ multi-velocity  │ │ samples   │
└───────────┘ └─────────────────┘ └───────────┘
```

### Instrument Base Class

```python
from abc import ABC, abstractmethod
import numpy as np

class Instrument(ABC):
    """Base class for all sound-producing instruments."""

    @abstractmethod
    def render(self, note: NoteEvent, sample_rate: int) -> np.ndarray:
        """Render a single note to audio samples.

        Args:
            note: The note event (pitch, duration, velocity)
            sample_rate: Audio sample rate (e.g., 44100)

        Returns:
            Mono audio samples as float32 array, normalized to [-1, 1]
        """
        ...
```

### Synth (Waveform Synthesizer)

Available in Phase 2. Generates audio from basic waveforms with ADSR envelopes.

```python
class Synth(Instrument):
    """Waveform-based synthesizer with ADSR envelope."""

    def __init__(
        self,
        waveform: str = "sine",      # sine, square, saw, triangle
        attack: float = 0.01,         # seconds
        decay: float = 0.1,           # seconds
        sustain: float = 0.7,         # level (0-1)
        release: float = 0.2,         # seconds
        filter: str | None = None,    # lowpass, highpass, or None
        cutoff: float = 1000,         # filter cutoff frequency (Hz)
    ): ...
```

**Preset Synths:**
- `SynthBass`: Saw wave, low cutoff, punchy envelope
- `SynthPad`: Triangle wave, slow attack, long release
- `SynthLead`: Square wave, fast attack, medium sustain

### InstrumentBank

Manages instrument assignment to tracks.

```python
class InstrumentBank:
    """Maps roles and track names to instruments."""

    def __init__(self, mapping: dict[Role | str, Instrument]):
        ...

    def get_instrument(self, track_name: str, role: Role | None) -> Instrument:
        """Get instrument for a track, checking name first, then role."""
        ...
```

### Default Instruments

When no `InstrumentBank` is provided, defaults are used:

| Role | Default Instrument |
|------|-------------------|
| `Role.BASS` | `Synth(waveform="saw", cutoff=400, attack=0.01)` |
| `Role.HARMONY` | `Synth(waveform="triangle", attack=0.05)` |
| `Role.MELODY` | `Synth(waveform="square", attack=0.01)` |
| `Role.RHYTHM` | `Synth(waveform="square", attack=0.001, decay=0.1)` |
| (no role) | `Synth(waveform="sine")` |

### Instrument Assignment in DSL

```python
# Via InstrumentBank (recommended for multiple tracks)
instruments = InstrumentBank({
    Role.BASS: Synth(waveform="saw"),
    "lead": Synth(waveform="square"),
})
p.play(instruments=instruments)

# Per-track in DSL (convenient for single overrides)
verse.track("bass", instrument=Synth(waveform="saw", cutoff=200))
```

---

## Extensibility Points

### Custom Patterns
```python
@pattern
def my_pattern(harmony: HarmonyIR, params: dict) -> list[NoteEvent]:
    """User-defined pattern generator."""
    ...
```

### Custom Passes
```python
@analysis_pass(dialect="score")
def my_analysis(score: Score) -> AnalysisResult:
    """User-defined analysis pass."""
    ...

@transform_pass(dialect="intent")
def my_transform(piece: Piece, **kwargs) -> Piece:
    """User-defined transform pass."""
    ...
```

### Custom Backends
```python
@backend
def my_backend(events: EventIR, path: str) -> None:
    """User-defined output format."""
    ...
```

### Custom Dialects
```python
@dialect("my_dialect")
class MyDialect:
    """User-defined analytical or style dialect."""
    operations = [...]
    types = [...]
    lifts_from = ["score"]  # Which dialects it can be produced from
    lowers_to = ["score"]   # Which dialects it can produce
```

---

## Design Decisions

Key architectural decisions and their rationale.

### Three-Tier IR: Intent, Score, Event

- Intent → Event alone has too large a semantic gap for meaningful analysis
- Score IR captures voice leading, voicing, articulation, and dynamics — where music theory lives
- Each tier has its own natural pitch representation (Roman numerals → named pitches → MIDI) and timing (bar counts → bar-relative beats → absolute beats)
- Enables analysis passes at the level where they're most natural (counterpoint at Score level, harmonic function at Intent level, groove at Event level)

### Dialect Framework (MLIR-Inspired)

- Fixed IR levels would require modifying core code for every new analytical perspective
- Framework approach lets musicologists define their own dialects without touching puLang core
- Standard dialects (Intent/Score/Event) provide the common compilation path
- Analytical dialects (Schenkerian, set theory, counterpoint) provide specialized views
- Style dialects (jazz, Baroque) provide specialized lowering strategies

### Serialization: JSON

- Human-readable, critical for debugging and AI interop
- Universal tooling (browsers, notebooks, every language)
- Score sizes are small (a complex piece is <10MB)
- Fractions serialized as strings: `"3/4"`, `"1/16"`

### Timing: Fractions (Exact Rationals)

- Use `fractions.Fraction` for exact beat positions (no rounding errors with triplets)
- **Intent IR:** Abstract (bar counts, beat durations)
- **Score IR:** Bar-relative (matches how musicians think)
- **Event IR:** Piece-relative beats (simpler for backends)

### Pitch Representation

| Layer | Representation | Example |
|-------|----------------|---------|
| pyPuLang DSL | `Pitch` objects (int subclass) | `C4`, `C4 + 2` |
| Intent IR | Roman numerals / pattern types | `"V"`, `"arp"` |
| Score IR | Scientific notation strings | `"C#4"` |
| Event IR | MIDI integers | `60` |

### Error Handling: Strict

- Fail fast on structural errors (e.g., harmony doesn't divide into section bars)
- Warnings for unusual but valid choices (e.g., bass pattern on melody role)
- No silent failures or auto-corrections

### API Style: Flexible

Support multiple styles in pyPuLang:
```python
# Method chaining
verse.track("bass").pattern(root_eighths).octave(-2)

# Separate statements
bass = verse.track("bass")
bass.pattern(root_eighths)
bass.octave(-2)

# All-in-one
verse.track("bass", pattern=root_eighths, octave=-2)
```

### Playback: Protocol-Based Backends

- **Protocol-based architecture** — All backends implement `PlaybackBackend` protocol
- **Extensible** — New backends can be added without changing core API
- **Global default + per-call override** — Flexible configuration
- **Built-in synth as default** — Zero external dependencies for basic playback

### Audio Output: sounddevice

- **Cross-platform** — Works on macOS, Windows, Linux
- **numpy integration** — Natural for waveform synthesis
- **Well-maintained** — Active development, good community
- **Callback-based API** — Suitable for real-time audio

### Instruments: Hierarchical Design

- **Base `Instrument` ABC** — All sound sources implement `render()`
- **`Synth`** — Waveform synthesis (Phase 2, no external deps)
- **`SampledInstrument`** — Bundled samples (Future, ~5-10 MB)
- **`Sampler`** — User samples (Future, user-provided files)
- **`InstrumentBank`** — Maps roles/names to instruments
- **Sensible defaults** — Each role has a default synth preset

### Direct Intent → Event Path

- A convenience `realize()` function lowers Intent → Event directly for simple use cases
- Internally, this routes through Score IR (Intent → Score → Event)
- Users can intercept at the Score level for analysis or transformation when needed

---

## Implementation Order

1. **Event IR + MIDI backend** — Get notes playing
2. **Intent IR + Realization** — Get patterns working
3. **One transform** — Prove the pipeline
4. **pyPuLang DSL** — Make it pleasant to write
5. **Score IR + two-step lowering** — Make the middle layer real
6. **Score-level passes** — Voice leading analysis, counterpoint checks
7. **Additional backends** — MusicXML (from Score IR), audio
8. **Additional transforms** — Build the library at each level
9. **Dialect framework** — Make the extension mechanism formal
10. **puLang standalone syntax** — Parser and frontend (after pyPuLang stabilizes)

This order ensures we have working, audible output at each stage, and the most valuable additions (Score IR and passes) come before the more speculative framework work.
