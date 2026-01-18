# puLang Architecture

## Overview

puLang uses a **compiler-style architecture** with clear separation between:
- **Frontends** — pyPuLang (Python DSL) and puLang (standalone syntax)
- **IR (Intermediate Representation)** — the musical data structures
- **Transforms** — passes that analyze or modify the IR
- **Backends** — emitters to MIDI, MusicXML, audio, etc.

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
│                         Intent IR                               │
│   Sections, Harmony, Patterns, Tracks, Roles                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ transforms (optional)
┌─────────────────────────────────────────────────────────────────┐
│                      Transform Pipeline                         │
│   reharmonize, voice_lead, thin_texture, transpose, ...        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ realization
┌─────────────────────────────────────────────────────────────────┐
│                          Event IR                               │
│   Concrete notes, durations, velocities, timings               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ emission
┌─────────────────────────────────────────────────────────────────┐
│                          Backends                               │
│   MIDI  │  MusicXML  │  Audio  │  JSON  │  LilyPond  │  ...    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Frontends

puLang has two frontends that emit identical IR.

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

---

## Layer 3: Transform Pipeline

### Design Principle
Transforms are **pure functions** that take IR and return IR. They can be composed and ordered.

### Transform Types

#### Harmonic Transforms
```python
def reharmonize(ir: SectionIR, strategy: str) -> SectionIR:
    """Replace chords using substitution strategies."""
    # modal_interchange, tritone_sub, secondary_dominant, etc.

def transpose(ir: PieceIR, interval: int) -> PieceIR:
    """Transpose entire piece."""

def modulate(ir: SectionIR, to_key: Key, pivot: RomanNumeral) -> SectionIR:
    """Introduce modulation."""
```

#### Textural Transforms
```python
def thin_texture(ir: SectionIR, except_roles: list[Role]) -> SectionIR:
    """Reduce density by removing notes."""

def thicken_texture(ir: SectionIR, strategy: str) -> SectionIR:
    """Add doublings, fill voicings."""

def change_register(ir: TrackIR, octaves: int) -> TrackIR:
    """Shift up/down."""
```

#### Voice Leading Transforms
```python
def voice_lead(ir: SectionIR, max_leap: int = 4) -> SectionIR:
    """Apply voice leading rules to chord voicings."""

def smooth_bass(ir: TrackIR) -> TrackIR:
    """Minimize bass movement."""
```

### Transform Ordering

Transforms may have dependencies:
1. Harmonic transforms first (change the chords)
2. Voice leading second (determine voicings)
3. Textural transforms third (adjust density)
4. Register transforms last (shift octaves)

The pipeline should either:
- Enforce ordering constraints
- Or let the user specify order explicitly

**Phase 1:** Explicit user ordering. Implicit ordering is a future enhancement.

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

### Realization: Intent IR → Event IR

This is where patterns become notes:

```python
def realize(intent: PieceIR) -> EventIR:
    """Convert Intent IR to Event IR."""
    events = []
    for section in intent.sections:
        for track in section.tracks:
            if isinstance(track.content, PatternIR):
                events.extend(realize_pattern(track, section.harmony))
            elif isinstance(track.content, NotesIR):
                events.extend(realize_notes(track))
    return EventIR(events=events, tempo=intent.tempo, ...)
```

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
def emit_musicxml(events: EventIR, path: str) -> None:
    """Write to MusicXML for notation software."""
```

### JSON Backend
```python
def emit_json(ir: PieceIR | EventIR, path: str) -> None:
    """Serialize IR for debugging/interchange."""
```

### Audio Backend (Future)
```python
def emit_audio(events: EventIR, path: str, soundfont: str) -> None:
    """Render to audio using FluidSynth or similar."""
```

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

### SampledInstrument (Future)

Bundled sample-based instruments with multi-velocity layers.

```python
class SampledInstrument(Instrument):
    """Pre-packaged sample-based instrument."""

    def __init__(self, name: str):
        """Load bundled instrument by name.

        Available instruments: "piano", "bass", "strings", "pad"
        """
        ...
```

### Sampler (Future)

User-defined sampler for custom sample libraries.

```python
class Sampler(Instrument):
    """User-defined sampler with custom samples."""

    def __init__(
        self,
        sample_map: dict[int | tuple[int, int], Path],
        velocity_layers: int = 1,
    ):
        """Create sampler from user-provided samples.

        Args:
            sample_map: Maps MIDI pitch (or pitch range) to sample file
            velocity_layers: Number of velocity layers per pitch
        """
        ...
```

### InstrumentBank

Manages instrument assignment to tracks.

```python
class InstrumentBank:
    """Maps roles and track names to instruments."""

    def __init__(self, mapping: dict[Role | str, Instrument]):
        """Create instrument bank.

        Args:
            mapping: Maps Role enums or track names to Instrument instances.
                     Track names take precedence over roles.

        Example:
            InstrumentBank({
                Role.BASS: Synth(waveform="saw", cutoff=400),
                Role.HARMONY: Synth(waveform="triangle"),
                "lead": Synth(waveform="square"),  # Track name override
            })
        """
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

### Custom Transforms
```python
@transform
def my_transform(ir: SectionIR, **kwargs) -> SectionIR:
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

---

## Future: Music IR Compatibility

The architecture is designed to evolve toward a shared Music IR:

1. **Intent IR** becomes a dialect of Music IR
2. **Event IR** becomes another dialect
3. Transforms become passes in the Music IR ecosystem
4. Other tools can emit/consume the same IR

This requires:
- IR serialization format (JSON Schema, Protobuf)
- Clear semantic definitions
- Language-agnostic IR design (no Python-isms in the IR)

---

## Design Decisions

Key architectural decisions and their rationale.

### Serialization: JSON

- Human-readable, critical for debugging and AI interop
- Universal tooling (browsers, notebooks, every language)
- Score sizes are small (a complex piece is <10MB)
- Fractions serialized as strings: `"3/4"`, `"1/16"`

### Timing: Fractions (Exact Rationals)

- Use `fractions.Fraction` for exact beat positions (no rounding errors with triplets)
- **Intent IR:** Bar-relative (matches how musicians think)
- **Event IR:** Piece-relative beats (simpler for backends)

### Pitch Representation

| Layer | Representation | Example |
|-------|----------------|---------|
| pyPuLang DSL | `Pitch` objects (int subclass) | `C4`, `C4 + 2` |
| Intent IR | Scientific notation strings | `"C#4"` |
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

---

## Implementation Order

1. **Event IR + MIDI backend** — Get notes playing
2. **Intent IR + Realization** — Get patterns working
3. **One transform** — Prove the pipeline
4. **pyPuLang DSL** — Make it pleasant to write
5. **Additional backends** — MusicXML, audio
6. **Additional transforms** — Build the library
7. **puLang standalone syntax** — Parser and frontend (after pyPuLang stabilizes)

This order ensures we have working, audible output at each stage.
