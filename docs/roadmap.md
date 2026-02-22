# puLang Roadmap

## Philosophy

**Build the minimum that proves the concept, then expand based on real usage.**

Each phase should produce something usable. If a phase doesn't result in composable, audible music, it's premature.

## Dual-Syntax Approach

puLang has **two distinct syntaxes** that share the same IR and semantics:

### pyPuLang — Python-Embedded DSL
- **What:** Python library with context managers, method chaining, and Pythonic constructs
- **For:** Programmers, AI/ML researchers, Jupyter notebooks, scripting
- **File type:** `.py` files
- **Example:**
  ```python
  with piece(tempo=120, key="C major") as p:
      verse = p.section("verse", bars=8)
      verse.harmony(I, IV, vi, V)
      verse.track("bass", role=Role.BASS).pattern(root_quarters)
  ```

### puLang — Standalone Music-Native Syntax
- **What:** Custom syntax designed for musicians, inspired by lead sheets and chord charts
- **For:** Musicians, composers, people who don't want to write Python
- **File type:** `.pu` files (future)
- **Spec:** See [pulang-syntax.md](pulang-syntax.md) for full specification
- **Example:**
  ```
  piece "Example"
    tempo: 120
    key: C

  tracks
    Bass [role=bass]

  section Verse [8 bars]
    harmony: I IV vi V

    Bass
      pattern: root_quarters
  ```

**Implementation order:** We build pyPuLang first to iterate on semantics, then implement the puLang parser once the IR stabilizes. Both syntaxes emit identical Intent IR.

---

## Phase 0: Foundation ✅

**Goal:** Documentation and design alignment.

### Checklist
- [x] Review notes capturing initial analysis
- [x] Positioning document
- [x] Architecture document
- [x] Language specification (draft)
- [x] IR specification (draft)
- [x] Roadmap (this document)

### Exit Criteria
- [x] Design is coherent and reviewed
- [x] No major architectural unknowns

---

## Phase 1: Minimal Playable Prototype

**Goal:** Compose an 8-bar piece and hear it.

### Architecture (Phase 1)

```
┌─────────────────────────────────────────┐
│           pyPuLang DSL                  │
│  piece() → section() → harmony/track   │
└─────────────────┬───────────────────────┘
                  │ .to_ir()
                  ▼
┌─────────────────────────────────────────┐
│             Intent IR                   │
│  pulang.ir.intent module:              │
│  Piece, Section, Harmony, Track, etc.  │
└─────────────────┬───────────────────────┘
                  │ realize_to_midi()
                  ▼
┌─────────────────────────────────────────┐
│     MIDI Output (via mido)              │
├─────────────────────────────────────────┤
│  p.save_midi("out.mid") → Write file    │
│  p.to_midi()         → Return MidiFile  │
└─────────────────────────────────────────┘
```

**Note:** Event IR is deferred to Phase 3. In Phase 1, we realize Intent IR directly to MIDI.

**IR Serialization:** Intent IR is JSON-serializable. pyPuLang keeps it in-memory for convenience, but standalone puLang will read/write IR as JSON files.

### 1.1 Project Structure
- [x] Create Python package: `pypulang/`
- [x] Set up `pyproject.toml` with metadata (hatch)
- [x] Add dependency: `mido` (MIDI file I/O)
- [x] Add dev dependencies: `pytest`, `hypothesis`
- [x] Verify `fractions` from stdlib works for timing

### 1.2 Intent IR (Minimal)

Module: `pypulang.ir.intent`

- [x] Define `Key` dataclass (root, mode)
- [x] Define `TimeSignature` dataclass (numerator, denominator)
- [x] Define `Chord` dataclass (numeral, quality, extensions, inversion)
- [x] Define `ChordChange` dataclass (chord, duration)
- [x] Define `Harmony` dataclass (changes, duration_unit)
- [x] Define `Pattern` dataclass (pattern_type, params)
- [x] Define `Track` dataclass (name, role, instrument, content, octave_shift, velocity)
- [x] Define `Section` dataclass (name, bars, key, time_signature, harmony, tracks)
- [x] Define `Piece` dataclass (title, tempo, key, time_signature, sections)
- [x] Implement JSON serialization for all types (optional, nice-to-have)

### 1.3 Chord Resolution
- [x] Implement `resolve_chord(chord: Chord, key: Key) -> list[int]`
- [x] Support major triads (I, IV, V, etc.)
- [x] Support minor triads (ii, iii, vi, etc.)
- [x] Support dominant 7ths (V7)
- [x] Support major keys
- [x] Support minor keys (natural minor)
- [x] Write tests for chord resolution (pytest + hypothesis)

### 1.4 First Pattern: `root_quarters`
- [x] Implement pattern registry (`PATTERN_REGISTRY` dict)
- [x] Implement `root_quarters` pattern generator
- [x] Pattern signature: `(chord_pitches, duration, offset, track_params) -> list[tuple]`
- [x] Returns list of `(pitch, start, duration, velocity)` tuples
- [x] Write test: pattern generates correct notes for I-IV-vi-V

### 1.5 Direct MIDI Emission
- [x] Implement `realize_to_midi(piece: Piece) -> mido.MidiFile`
- [x] Walk sections, resolve chords, generate pattern notes
- [x] Convert beat positions to MIDI ticks
- [x] Create MIDI tracks from puLang tracks
- [x] Set tempo and time signature
- [x] Write test: PieceIR → valid MIDI file

### 1.6 pyPuLang DSL (Minimal)
- [x] Implement `piece()` context manager
- [x] Implement `Piece.section(name, bars)` method
- [x] Implement `Section.harmony(*chords)` method
- [x] Implement `Section.progression(*chords)` as alias for `harmony()`
- [x] Implement `Section.track(name, role, instrument)` method
- [x] Implement `Track.pattern(pattern_type, **params)` method
- [x] Implement `Track.octave(n)` method
- [x] Implement `Piece.save_midi(path)` — write MIDI file
- [x] Implement `Piece.to_midi()` — return `mido.MidiFile` object
- [x] Implement `Piece.to_ir()` — return `ir.intent.Piece`
- [x] Define roman numeral constants: `I, II, III, IV, V, VI, VII` (and lowercase)
- [x] Define `Role` enum: `MELODY, BASS, HARMONY, RHYTHM`
- [x] Define `root_quarters` pattern singleton

### 1.7 puLang Standalone Syntax (Design Only)
- [x] Draft equivalent standalone syntax (see [pulang-syntax.md](pulang-syntax.md))
- [x] Ensure semantic alignment with pyPuLang
- [x] No parser implementation yet (deferred to future phase)

### Test Composition (Phase 1)

```python
from pypulang import *

with piece(tempo=100, key="C major") as p:
    verse = p.section("verse", bars=4)
    verse.harmony(I, IV, vi, V)
    verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

# Write to file
p.save_midi("test.mid")

# Or get MidiFile object for external playback
midi = p.to_midi()
```

### Equivalent puLang Syntax (Design Only)

```
piece "Test Composition"
  tempo: 100
  key: C
  time: 4/4

tracks
  Bass [role=bass]

section Verse [4 bars]
  harmony: I IV vi V

  Bass
    pattern: root_quarters
    octave: -1
```

See [pulang-syntax.md](pulang-syntax.md) for the full standalone syntax specification.

### Exit Criteria
- [x] Test composition produces valid MIDI file
- [x] MIDI file plays correctly in external player (user's responsibility)
- [x] Bass plays the root of each chord on each beat
- [x] `to_midi()` returns usable `mido.MidiFile` object

---

## Phase 2: Patterns, Escape Hatch, and Live Playback

**Goal:** Multiple patterns, literal notes support, and real-time playback for rapid prototyping.

### 2.1 Additional Patterns ✅
- [x] Implement `root_eighths` pattern (root note in eighth notes)
- [x] Implement `root_fifths` pattern (root + fifth alternating)
- [x] Implement `arp` pattern with `direction` parameter
  - [x] `arp("up")` — ascending arpeggio
  - [x] `arp("down")` — descending arpeggio
  - [x] `arp("updown")` — ascending then descending
- [x] Implement `block_chords` pattern (chord hits)

### 2.2 Pattern Parameters ✅
- [x] Add `rate` parameter to patterns (1/4, 1/8, 1/16)
- [x] Add `octave_shift` parameter to patterns
- [x] Add `velocity` parameter to patterns
- [x] Support builder-style pattern configuration: `arp.up().rate(1/16)`

### 2.3 Escape Hatch (Literal Notes) ✅
- [x] Implement `Track.notes(note_list)` method
- [x] Define pitch constants module: `C4, D4, E4, ...` (all octaves 0-8)
- [x] Define sharp/flat variants: `Cs4, Db4, ...`
- [x] Implement `Pitch` class (int subclass with arithmetic)
- [x] Support tuple syntax: `(C4, 1/4)` for note + duration
- [x] Implement `note(pitch, duration, velocity=None)` function
- [x] Implement `rest(duration)` function
- [x] Implement `chord(pitches, duration)` function for simultaneous notes
- [x] Define `Notes` dataclass in `ir.intent` for literal notes

### 2.4 Live Playback System

**Goal:** Real-time audio playback for rapid prototyping with transport controls, using a built-in synthesis engine.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      pypulang Playback API                       │
├─────────────────────────────────────────────────────────────────┤
│  p.play()      → Play once                                      │
│  p.loop()      → Loop until stopped                             │
│  p.loop(section="verse")  → Loop specific section               │
│  p.play(from_bar=5)       → Start from bar 5                    │
│  p.stop()      → Stop playback                                  │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PlaybackBackend Protocol                      │
│  All backends implement: play(), stop(), pause(), resume(),     │
│  is_available(), is_playing()                                   │
└─────────────────┬───────────────────────────────────────────────┘
                  │
      ┌───────────┴───────────────────┐
      ▼                               ▼
┌─────────────────────┐     ┌─────────────────────┐
│   BuiltinSynth      │     │   VirtualMidi       │
│   (Default)         │     │   Port → DAW        │
│                     │     │                     │
│ - Waveform synth    │     │ - python-rtmidi     │
│ - Sampled instr.    │     │ - Route to DAW      │
│ - sounddevice out   │     │ - Pro instruments   │
└─────────────────────┘     └─────────────────────┘
```

#### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Default backend | Built-in synth | Zero-config playback, no external dependencies for basic use |
| Audio library | `sounddevice` | Cross-platform, numpy integration, well-maintained |
| Backend selection | Global config + per-call override | Flexible: set once or override as needed |
| Backend interface | Protocol-based | Extensible for future backends without changing core API |
| Sample format | One-shot, multi-velocity | Good quality/size tradeoff (~5-10 MB) |

#### 2.4.1 Playback Backend Protocol
- [x] Define `PlaybackBackend` protocol with standard interface
- [x] Define `PlaybackHandle` for transport control of active playback
- [x] Implement backend auto-detection and fallback
- [x] Implement global default backend configuration
- [x] Implement per-call backend override

```python
class PlaybackBackend(Protocol):
    def play(self, events: EventStream, instruments: InstrumentBank) -> PlaybackHandle: ...
    def is_available(self) -> bool: ...
    def name(self) -> str: ...

class PlaybackHandle(Protocol):
    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def is_playing(self) -> bool: ...
```

#### 2.4.2 Built-in Synth Backend (Default)
- [x] Add `sounddevice` as core dependency (changed from optional)
- [x] Implement `BuiltinSynth` backend class
- [x] Implement waveform synthesis (sine, square, saw, triangle)
- [x] Implement ADSR envelope generator
- [x] Implement basic filters (lowpass, highpass)
- [x] Implement real-time audio mixing for multiple tracks
- [ ] Target latency: <50ms from play() to sound

#### 2.4.3 Instrument System (Synth Only - Phase 2)
- [x] Define `Instrument` base class/protocol
- [x] Implement `Synth` class for waveform-based instruments
  - [x] Configurable waveform, ADSR, filter parameters
  - [x] Preset synths: `SynthBass`, `SynthPad`, `SynthLead`
- [x] Implement `InstrumentBank` for instrument assignment
- [x] Support assignment by role: `{Role.BASS: Synth(...)}`
- [x] Support assignment by track name: `{"lead": Synth(...)}`
- [ ] Support per-track override in DSL: `track("bass", instrument=Synth(...))`
- [x] Define sensible default instruments per role

```python
# Instrument base class
class Instrument(ABC):
    @abstractmethod
    def render(self, note: NoteEvent, sample_rate: int) -> np.ndarray: ...

# Waveform synthesizer
class Synth(Instrument):
    def __init__(
        self,
        waveform: str = "sine",  # sine, square, saw, triangle
        attack: float = 0.01,
        decay: float = 0.1,
        sustain: float = 0.7,
        release: float = 0.2,
        filter: str | None = None,
        cutoff: float = 1000,
    ): ...

# Instrument assignment
instruments = InstrumentBank({
    Role.BASS: Synth(waveform="saw", cutoff=400),
    Role.HARMONY: Synth(waveform="triangle"),
    "lead": Synth(waveform="square"),
})
p.play(instruments=instruments)
```

#### 2.4.4 Transport Controls
- [x] Implement `p.play()` — play piece once
- [x] Implement `p.stop()` — stop playback
- [x] Implement `p.pause()` / `p.resume()` — pause/resume (via handle)
- [x] Implement `p.loop(count=None)` — loop N times or forever
- [x] Implement `p.play(from_bar=N)` — start from specific bar
- [x] Implement `p.play(section="verse")` — play specific section
- [x] Implement `p.loop(section="verse", bars=4)` — loop section/bars

#### 2.4.5 Virtual MIDI Port Backend (DAW Integration)
- [x] Add `python-rtmidi` as core dependency (changed from optional)
- [x] Implement `VirtualMidi` backend class
- [x] Implement `p.connect(port="pypulang")` — create virtual MIDI port
- [x] Implement `p.list_ports()` — list available MIDI outputs
- [x] Implement `p.disconnect()` — close virtual port
- [x] Document IAC Driver setup (macOS)
- [x] Document loopMIDI setup (Windows)
- [x] Document ALSA virtual ports (Linux)
- [x] Support routing to existing MIDI ports

#### 2.4.6 Hot Reload (Advanced) ✅
- [x] Implement file watcher for `.py` source files
- [x] Auto-reload and restart playback on save
- [x] Preserve playback position across reloads (best effort)
- [x] `p.watch()` — enable hot reload mode

### 2.5 Drums and Percussion ✅

**Goal:** First-class support for drums and percussion, using existing track/pattern infrastructure.

#### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Drum track type | Regular track with `role=Role.RHYTHM` | Minimal new API; drums are just tracks that ignore harmony |
| Drum sounds | Named constants mapping to GM drum map | `KICK`, `SNARE`, `HIHAT` more readable than MIDI numbers |
| Drum patterns | Pattern functions like melodic patterns | Consistent API; `rock_beat`, `four_on_floor`, etc. |
| MIDI channel | Auto-assign channel 10 for rhythm role | GM standard; transparent to user |
| Default sound | Bundled synthetic samples (CC0) | Zero-config drum playback; fallback to synthesis if samples unavailable |
| Sample format | OGG Vorbis (~60KB total) | Good compression, sufficient quality, small footprint |

#### 2.5.1 Drum Sound Constants ✅
- [x] Define `pypulang.drums` module
- [x] Define GM drum map constants:
  - [x] `KICK` (36), `KICK2` (35)
  - [x] `SNARE` (38), `SNARE2` (40), `RIMSHOT` (37), `CLAP` (39)
  - [x] `HIHAT_CLOSED` (42), `HIHAT_OPEN` (46), `HIHAT_PEDAL` (44)
  - [x] `TOM_LOW` (45), `TOM_MID` (47), `TOM_HIGH` (50)
  - [x] `CRASH` (49), `CRASH2` (57), `RIDE` (51), `RIDE_BELL` (53)
  - [x] `TAMBOURINE` (54), `COWBELL` (56), `SHAKER` (70)
- [x] Ensure drum constants work with existing `notes()` escape hatch

#### 2.5.2 Basic Drum Patterns ✅
- [x] Implement `rock_beat` pattern (kick on 1/3, snare on 2/4, hihats on 8ths)
- [x] Implement `four_on_floor` pattern (kick on every beat)
- [x] Implement `backbeat` pattern (snare on 2/4 only)
- [x] Implement `eighth_hats` pattern (hihat only, eighth notes)
- [x] Implement `shuffle` pattern (swung hihat with kick/snare)
- [x] Pattern parameters: `hihat` (closed/open), `tempo_feel` (straight/swing)

#### 2.5.3 Drum Sample System ✅
- [x] Implement `DrumSampler` instrument class
- [x] Add bundled drum samples (kick, snare, hihat_closed, hihat_open, crash, ride)
- [x] Generate synthetic CC0 samples using NumPy (~60KB total)
- [x] Add `soundfile` dependency for sample loading
- [x] Implement sample caching for performance
- [x] Implement synthesis fallback when samples unavailable
- [x] Create sample generation utility (`scripts/generate_drum_samples.py`)
- [x] Document sample attribution and licensing

#### 2.5.4 Drum Track Integration ✅
- [x] Auto-assign MIDI channel 10 for `Role.RHYTHM` tracks
- [x] Drum patterns ignore harmony (don't receive chord context)
- [x] Support velocity per hit in patterns
- [x] Fix role information passing through playback pipeline
- [x] `DrumSampler` automatically used for rhythm role tracks

#### 2.5.5 Grid Notation (Optional Sugar - Deferred)
- [ ] Implement `drums()` context manager / block
- [ ] Support string-based grid patterns: `"x...x...x...x..."`
- [ ] `x` = hit, `.` = rest, `o` = accent, `-` = ghost note
- [ ] Grid resolution from section or explicit `grid` parameter
- [ ] Each drum sound is a "lane": `d.kick("x...x...")`, `d.snare("....x...")`

```python
# Grid notation example (future)
with verse.drums(grid=1/16) as d:
    d.kick("x...x...x...x...")
    d.snare("....x.......x...")
    d.hihat("x.x.x.x.x.x.x.x.")
```

### 2.6 Second Test Composition ✅
- [x] Compose 16-bar piece with verse + chorus structure
- [x] Use multiple patterns across tracks
- [x] Use escape hatch for melody line
- [x] **Include drum track with rock_beat pattern**
- [ ] Test live playback with looping
- [x] Verify all patterns sound correct

### Test Composition (Phase 2)

```python
from pypulang import *
from pypulang.pitches import *
from pypulang.playback import Synth, InstrumentBank, VirtualMidi

with piece(tempo=120, key="G major") as p:
    verse = p.section("verse", bars=8)
    verse.harmony(I, vi, IV, V)
    verse.track("bass", role=Role.BASS).pattern(root_eighths).octave(-2)
    verse.track("keys").pattern(arp("up"), rate=1/16)
    verse.track("melody").notes([
        (D5, 1/4), (E5, 1/4), (G5, 1/2),
        (A5, 1/4), (G5, 1/4), (E5, 1/2),
        # ... more melody
    ])

    chorus = p.section("chorus", bars=8)
    chorus.harmony(IV, V, I, vi)
    chorus.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
    chorus.track("keys").pattern(block_chords, rate=1/2)

# File output (existing)
p.save_midi("song.mid")

# Live playback with built-in synth (new)
p.play()                      # Play once with default synth instruments
p.loop(section="verse")       # Loop verse while tweaking
p.play(from_bar=9)            # Jump to chorus

# Custom instruments (new)
instruments = InstrumentBank({
    Role.BASS: Synth(waveform="saw", cutoff=400),
    Role.HARMONY: Synth(waveform="triangle"),
})
p.play(instruments=instruments)

# DAW integration via virtual MIDI (new)
p.connect(port="pypulang")    # Create virtual MIDI port
p.play(backend=VirtualMidi("pypulang"))  # Route to DAW
```

### Exit Criteria
- [x] Can compose recognizable 16-bar piece
- [x] Multiple tracks with different patterns
- [x] Escape hatch works for literal melodies
- [x] All patterns produce correct MIDI output
- [x] `p.play()` plays audio through built-in synth
- [x] `p.loop()` loops playback until stopped
- [x] Custom `Synth` instruments work with configurable waveforms and envelopes
- [x] `InstrumentBank` allows per-role and per-track instrument assignment
- [x] `p.connect()` creates virtual MIDI port for DAW routing

### 2.7 Audio Export
- [ ] Implement `p.save_audio(path)` — render audio to a `.wav` file
- [ ] Route internal event stream through `BuiltinSynth`
- [ ] Export directly to file without real-time recording

---

## Phase 3: Transforms, Score IR, and Event IR

**Goal:** Prove the transform pipeline works. Introduce Score IR and Event IR, establishing the full three-tier compilation path.

### Architecture (Phase 3)

```
┌─────────────────────────────────────────┐
│           pyPuLang DSL                  │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│           Intent IR                     │
│  pulang.ir.intent module               │
└─────────────────┬───────────────────────┘
                  │ intent-level transforms (optional)
                  ▼
┌─────────────────────────────────────────┐
│      Transformed Intent IR              │
└─────────────────┬───────────────────────┘
                  │ lower_to_score() — voicing, voice leading
                  ▼
┌─────────────────────────────────────────┐
│           Score IR                      │
│  pulang.ir.score module                │
│  Parts, Bars, Named pitches, Voices,   │
│  Dynamics, Articulation                │
└─────────────────┬───────────────────────┘
                  │ score-level transforms (optional)
                  │ lower_to_events() — performance interpretation
                  ▼
┌─────────────────────────────────────────┐
│           Event IR                      │
│  pulang.ir.event module                │
└─────────────────┬───────────────────────┘
                  │ emit_midi()
                  ▼
┌─────────────────────────────────────────┐
│           MIDI Output                   │
└─────────────────────────────────────────┘
```

### 3.1 Score IR

Module: `pulang.ir.score`

Score IR captures realized musical content — specific pitches in specific voices with articulation and dynamics. This is the level at which music theory analysis operates.

- [ ] Define `Score` dataclass (title, tempo, key, time_signature, parts, sections)
- [ ] Define `Part` dataclass (name, role, instrument, bars)
- [ ] Define `Bar` dataclass (number, key, time_signature, notes)
- [ ] Define `ScoreNote` dataclass (pitch, beat, duration, dynamic, articulation, tie, voice)
- [ ] Define `ScoreSection` dataclass (name, start_bar, end_bar)
- [ ] Implement JSON serialization for all Score IR types
- [ ] Implement `lower_to_score(piece: intent.Piece) -> Score` — Intent → Score lowering
- [ ] Pattern realization produces Score IR bars (not Event IR events directly)
- [ ] Voice leading decisions happen during Intent → Score lowering
- [ ] **Escape Hatch Semantics:** Define precisely how literal notes (`Track.notes()`) are handled during lowering. Should they bypass voice-leading transformations completely (i.e., pass-through), or be subject to them? Add a `locked=True` parameter to literal notes to prevent unwanted modifications during Score-level passes.

### 3.2 Event IR

Module: `pulang.ir.event`

- [ ] Define `NoteEvent` dataclass (pitch, start, duration, velocity, track)
- [ ] Define `RestEvent` dataclass (start, duration, track)
- [ ] Define `ControlEvent` dataclass (control_type, value, time, track)
- [ ] Define `EventStream` dataclass (tempo, time_signature, events)
- [ ] Implement `lower_to_events(score: Score) -> EventStream` — Score → Event lowering
- [ ] Implement dynamic → velocity mapping
- [ ] Implement articulation → duration adjustment
- [ ] Implement `emit_midi(events: EventStream) -> mido.MidiFile`
- [ ] Refactor Phase 1-2 code to route through Score IR internally
- [ ] Provide convenience `realize_to_midi()` that internally routes through Intent → Score → Event

### 3.2 Transform Infrastructure
- [ ] Define `Transform` protocol/interface
- [ ] Implement `apply(ir, *transforms) -> ir` function
- [ ] Transforms receive Intent IR and return new Intent IR
- [ ] Ensure transforms are pure (no mutation)
- [ ] Document transform ordering constraints

### 3.3 `transpose` Transform
- [ ] Implement `transpose(semitones: int)` transform
- [ ] Shifts key center by semitones
- [ ] Roman numerals stay the same, key changes
- [ ] Works on `SectionIR` or `PieceIR`
- [ ] Write tests for transpose

### 3.4 `register` Transform
- [ ] Implement `register(octaves: int)` transform
- [ ] Shifts all tracks by octave amount
- [ ] Can target specific tracks/roles
- [ ] Write tests for register shift

### 3.5 Section Transform Syntax
- [ ] Implement `Section.transform(**kwargs)` method
- [ ] Returns new section (immutable operation)
- [ ] Support `transpose` parameter
- [ ] Support `register` parameter
- [ ] Original section unchanged after transform

### 3.6 Third Test Composition
- [ ] Create verse section
- [ ] Create bridge as transposed verse: `bridge = verse.transform(transpose=5)`
- [ ] Structure: verse → bridge → verse
- [ ] Verify transform produces correct output

### Test Composition (Phase 3)

```python
from pulang import *

with piece(tempo=100, key="C major") as p:
    verse = p.section("verse", bars=8)
    verse.harmony(I, IV, vi, V)
    verse.track("bass", role=Role.BASS).pattern(root_eighths).octave(-2)
    verse.track("keys").pattern(arp("up"), rate=1/16)

    # Bridge is verse transposed up a 4th
    bridge = verse.transform(transpose=5)
    bridge.name = "bridge"

    p.form([verse, bridge, verse])

p.save_midi("with_transform.mid")
```

### Exit Criteria
- [ ] Can create transformed section from existing section
- [ ] Transform produces musically correct output
- [ ] Full pipeline works: DSL → Intent IR → Transform → Score IR → Event IR → MIDI
- [ ] Score IR is inspectable: can see specific pitches per voice, bar by bar
- [ ] Original section unchanged after transform
- [ ] Both Score IR and Event IR are serializable to JSON
- [ ] Convenience `realize_to_midi()` works (routes through Score IR internally)

---

## Phase 4: Richer Harmony and Advanced Patterns

**Goal:** Handle real-world chord progressions and add harmony-aware patterns.

### 4.1 Harmony-Aware Patterns

These patterns require richer harmony context (chord tones, passing tones, voice leading).

#### 4.1.1 Walking Bass Pattern
- [ ] Implement `walking_bass` pattern
- [ ] Walk through chord tones with chromatic/diatonic approach notes
- [ ] Quarter-note based (standard jazz walking bass)
- [ ] Parameters: `approach` (chromatic/diatonic), `range` (octave span)
- [ ] Respects chord changes and inversions

```python
verse.track("bass", role=Role.BASS).pattern(walking_bass)
verse.track("bass").pattern(walking_bass(approach="chromatic"))
```

#### 4.1.2 Strum Pattern
- [ ] Implement `strum` pattern for guitar-style strumming
- [ ] Chord voicings with slight timing offsets (strum effect)
- [ ] Parameters: `direction` (down/up/alternate), `rate`, `mute` (palm mute)
- [ ] Support strum patterns: `"D.DU.UDU"` (D=down, U=up, .=rest)

```python
verse.track("guitar", role=Role.HARMONY).pattern(strum("D.DU.UDU"))
verse.track("guitar").pattern(strum.down().rate(1/8))
```

#### 4.1.3 Alberti Bass Pattern
- [ ] Implement `alberti` pattern (classical broken chord accompaniment)
- [ ] Pattern: root-fifth-third-fifth (or variants)
- [ ] Parameters: `variant` (standard/broken/arpeggiated)

### 4.2 Extended Chord Types
- [ ] Add 7th chord support: `V7`, `IVmaj7`, `ii7`, `vii7`
- [ ] Add major 7th: `.maj7()` modifier
- [ ] Add minor 7th: `.min7()` modifier
- [ ] Add suspended chords: `.sus2()`, `.sus4()`
- [ ] Add diminished: `.dim()` or `vii°`
- [ ] Add augmented: `.aug()` or `III+`
- [ ] Add 9th extensions: `.add9()`
- [ ] Add 11th extensions: `.add11()`
- [ ] Update `resolve_chord` for all new types

### 4.2 Secondary Dominants
- [ ] Support `V/V` (V of V) syntax
- [ ] Support `V/vi`, `V/ii`, `V/IV` etc.
- [ ] Implement secondary dominant resolution in `resolve_chord`
- [ ] Write tests for secondary dominants

### 4.3 Inversions
- [ ] Implement `.inv(n)` method on chords
- [ ] `I.inv(0)` — root position
- [ ] `I.inv(1)` — first inversion
- [ ] `I.inv(2)` — second inversion
- [ ] Correct bass note selection for inversions
- [ ] Write tests for inversions

### 4.4 Modal Keys
- [ ] Add Dorian mode support
- [ ] Add Phrygian mode support
- [ ] Add Lydian mode support
- [ ] Add Mixolydian mode support
- [ ] Add Aeolian (natural minor) mode support
- [ ] Add Locrian mode support
- [ ] Correct scale degree calculation for each mode
- [ ] Write tests for modal harmony

### 4.5 Fourth Test Composition
- [ ] Compose jazz-influenced piece
- [ ] Use secondary dominants (e.g., `V/V → V → I`)
- [ ] Use extended chords (7ths, 9ths)
- [ ] Use at least one inversion
- [ ] Verify all harmony sounds correct

### Test Composition (Phase 4)

```python
from pypulang import *

with piece(tempo=88, key="F major") as p:
    jazz = p.section("jazz", bars=8)
    jazz.harmony(
        (IVmaj7, 2),
        (V/V, 1), (V7, 1),
        (iii7, 1), (vi7, 1),
        (ii7, 1), (V7.inv(1), 1)
    )
    # Walking bass using new harmony-aware pattern
    jazz.track("bass", role=Role.BASS).pattern(walking_bass).octave(-2)
    jazz.track("piano").pattern(block_chords, rate=1/2)

    # Guitar with strum pattern
    jazz.track("guitar", role=Role.HARMONY).pattern(strum("D.DU.UDU"))

p.play()
```

### Exit Criteria
- [ ] Can express common jazz/pop progressions
- [ ] Secondary dominants resolve correctly
- [ ] Inversions produce correct bass notes
- [ ] Modal compositions work
- [ ] `walking_bass` produces musically correct walking lines
- [ ] `strum` pattern produces guitar-like chord voicings with timing offsets
- [ ] `alberti` pattern works for classical accompaniment

---

## Phase 5: Voice Leading Transform and Score-Level Passes

**Goal:** The first "intelligent" transform, operating on Score IR. First score-level analysis passes.

### 5.1 Voice Leading Algorithm
- [ ] Research voice leading algorithms (constraint satisfaction, heuristics)
- [ ] Implement basic voice leading: minimize total voice movement
- [ ] Add voice range constraints (SATB ranges)
- [ ] Add parallel fifth/octave avoidance (optional flag)
- [ ] Write tests for voice leading quality

### 5.2 `voice_lead` Transform (Score-Level)
- [ ] Implement `voice_lead(max_leap=5, avoid_parallels=True)` as a Score IR transform pass
- [ ] Operates on Score IR parts (not Intent IR tracks)
- [ ] Preserves bass line (role=BASS)
- [ ] Returns new Score with optimized voicings
- [ ] Write tests comparing before/after

### 5.2b First Score-Level Analysis Passes
- [ ] Implement `parallel_fifths_check` analysis pass — detect parallel fifths/octaves
- [ ] Implement `range_check` analysis pass — check each part against standard ranges
- [ ] Implement `voice_crossing_check` analysis pass — detect voice crossing
- [ ] Analysis passes return structured results (location, severity, description)

### 5.3 Voicing Hints
- [ ] Implement `.open()` method for open voicing
- [ ] Implement `.close()` method for close voicing
- [ ] Implement `.drop2()` for drop-2 voicing (jazz)
- [ ] Default: let voice leading decide
- [ ] Write tests for voicing hints

### 5.4 Fifth Test Composition
- [ ] Compose four-part chorale-style piece
- [ ] Apply voice leading transform
- [ ] Compare MIDI output before/after transform
- [ ] Verify noticeable improvement in smoothness

### Test Composition (Phase 5)

```python
from pulang import *

with piece(tempo=72, key="C major") as p:
    chorale = p.section("chorale", bars=8)
    chorale.harmony(I, IV, vi, V, I.inv(1), ii, V7, I)
    chorale.track("soprano", role=Role.MELODY)
    chorale.track("alto", role=Role.HARMONY)
    chorale.track("tenor", role=Role.HARMONY)
    chorale.track("bass", role=Role.BASS)

    # Apply voice leading
    voiced = chorale.transform(voice_lead(max_leap=4, avoid_parallels=True))

p.save_midi("chorale_raw.mid")
voiced_piece = piece.from_section(voiced)
voiced_piece.save_midi("chorale_voiced.mid")
```

### Exit Criteria
- [ ] Voice leading produces smooth, musical voicings
- [ ] Noticeable improvement over naive chord stacking
- [ ] Transform is configurable (max_leap, avoid_parallels)
- [ ] Works correctly with inversions

---

## Phase 6: Lifting (Analysis) Pipeline

**Goal:** Prove the "two-way street" by parsing external performance data and lifting it back into the IR tiers for analysis.

### 6.1 Event IR Lifting
- [ ] Implement `parse_midi(path: str) -> EventStream`
- [ ] Read standard MIDI files into Event IR (ticks to exact fractions where possible based on tempo map)

### 6.2 Score IR Lifting (Transcription)
- [ ] Implement `lift_to_score(events: EventStream) -> Score`
- [ ] Basic quantization to snap events to a grid
- [ ] Basic voice separation (heuristics to group events into parts/voices)
- [ ] Identify bar boundaries and time signatures

### 6.3 Intent IR Lifting (Analysis)
- [ ] Implement `lift_to_intent(score: Score) -> intent.Piece`
- [ ] Harmonic analysis pass: infer chords from Score notes
- [ ] Form detection: attempt to chunk bars into logical sections (A/B form)

### Exit Criteria
- [ ] Can load a basic, quantized MIDI file and reconstruct its basic structural intent.
- [ ] The full cycle (Intent -> Score -> Event -> MIDI -> Event -> Score -> Intent) works for simple material without massive information loss.

---

## Phase 7: MusicXML Backend

**Goal:** Output to notation software. Score IR makes this natural — it already has bar structure, named pitches, voices, dynamics, and articulation.

### 6.1 MusicXML Emitter
- [ ] Research MusicXML format specification
- [ ] Implement `emit_musicxml(score: Score, path: str)` — emit from Score IR (not Event IR)
- [ ] Output basic elements: notes, rests
- [ ] Output time signature
- [ ] Output key signature
- [ ] Output tempo marking
- [ ] Handle multiple tracks/parts

### 6.2 Notation Hints in IR
- [ ] Add `tie` property to notes spanning bar lines
- [ ] Add beam group hints (optional)
- [ ] Preserve track names as part names
- [ ] Handle voice assignment for multi-voice parts

### 6.3 Notation Software Testing
- [ ] Test output in MuseScore (free, cross-platform)
- [ ] Test output in Finale (if available)
- [ ] Test output in Dorico (if available)
- [ ] Verify: notes are correct
- [ ] Verify: rhythms are correct
- [ ] Verify: key/time signatures display correctly
- [ ] Fix any rendering issues

### Exit Criteria
- [ ] Can export to MusicXML with `p.save("output.xml")`
- [ ] Opens correctly in at least one notation app (MuseScore)
- [ ] Notes, rhythms, key signature, time signature are correct
- [ ] Multi-part scores render properly

---

## Phase 8: Real Compositions

**Goal:** Validate with actual music.

### 7.1 Composition 1: Pop Style
- [ ] 32+ bars
- [ ] Verse/chorus/bridge structure
- [ ] Use patterns: bass, chords, arpeggios
- [ ] Use escape hatch for melody
- [ ] Use transforms for variation

### 7.2 Composition 2: Jazz Style
- [ ] 32+ bars (e.g., AABA form)
- [ ] Use extended harmony (7ths, alterations)
- [ ] Use secondary dominants
- [ ] Use walking bass pattern
- [ ] Apply voice leading transform

### 7.3 Composition 3: Classical Style
- [ ] 32+ bars
- [ ] Use modal harmony
- [ ] Use voice leading transform
- [ ] Export to MusicXML
- [ ] Verify notation is readable

### 7.4 Stress-Test Report
- [ ] Document what worked well
- [ ] Document what felt awkward
- [ ] Document what's missing
- [ ] List syntax pain points
- [ ] List performance issues
- [ ] List missing patterns/transforms

### 7.5 Language Refinements
- [ ] Address syntax pain points from report
- [ ] Add requested patterns
- [ ] Fix performance issues
- [ ] Update documentation

### Exit Criteria
- [ ] Three compositions you'd actually listen to
- [ ] Clear list of pain points documented
- [ ] Language refinements implemented
- [ ] Roadmap for next phase based on real usage

---

## Phase 9: Dialect Framework and Pass Ecosystem

**Goal:** Formalize the MLIR-inspired dialect framework so users can define their own dialects, passes, and lowering/lifting strategies. This stabilizes the API for third-party extensions.

#### Dialect Framework Infrastructure
- [ ] Define `Dialect` protocol (operations, types, validate)
- [ ] Implement dialect registry
- [ ] Implement pass registry (analysis passes, transform passes per dialect)
- [ ] Implement lowering/lifting framework (dialect → dialect conversion)
- [ ] Define `@dialect`, `@analysis_pass`, `@transform_pass` decorators
- [ ] Pass composition: `pipe(pass1, pass2, pass3)` for chaining passes

#### First Analytical Dialect: Counterpoint
- [ ] Define counterpoint dialect operations (species, intervals, motion types, violations)
- [ ] Implement lifting from Score IR to counterpoint dialect
- [ ] Implement species identification
- [ ] Implement parallel fifths/octaves detection (migrate from Score-level pass)
- [ ] Implement voice independence analysis

#### Style-Specific Lowering
- [ ] Implement style parameter for Intent → Score lowering
- [ ] `style="default"` — common-practice voice leading rules
- [ ] `style="jazz"` — jazz voicing conventions (shell voicings, drop-2, rootless)
- [ ] `style="baroque"` — figured bass realization conventions
- [ ] Style-specific lowering as pluggable pass packages

#### Pass Ecosystem
- [ ] Document how to create and register custom passes
- [ ] Document how to create and register custom dialects
- [ ] Support `pip install pulang-<dialect>` pattern for community dialects
- [ ] Example: `pulang-schenkerian` — Schenkerian analysis dialect
- [ ] Example: `pulang-settheory` — pitch class set theory dialect

---

## Future Phases (Unscheduled)

These are ideas, not commitments. Check off if/when implemented.

### Sampled Instruments and Advanced Playback

**Goal:** Higher-quality instrument sounds via samples and external synth engines.

#### Bundled Sample Library
- [ ] Bundle core instrument samples (~5-10 MB compressed)
- [ ] One-shot samples with multiple velocity layers (3-4 layers)
- [ ] Core instruments: Piano, Bass, Strings, Pad
- [ ] Sample format: OGG (good compression, sufficient quality)
- [ ] Implement `SampledInstrument` class for bundled samples
- [ ] Automatic pitch-shifting for full range coverage

```python
class SampledInstrument(Instrument):
    """Pre-packaged sample-based instrument."""
    def __init__(self, name: str):  # "piano", "bass", "strings"
        # Loads from bundled samples
        ...
```

#### User Sampler
- [ ] Implement `Sampler` class for user-provided samples
- [ ] Support sample mapping by pitch range
- [ ] Support velocity layer mapping
- [ ] Support loop points for sustained sounds

```python
class Sampler(Instrument):
    """User-defined sampler with custom samples."""
    def __init__(self, sample_map: dict[int | tuple[int, int], Path]):
        # Maps MIDI pitches (or ranges) to sample files
        ...
```

#### FluidSynth Backend
- [ ] Add `pyfluidsynth` as optional dependency (`pypulang[fluidsynth]`)
- [ ] Implement `FluidSynthBackend` class
- [ ] Support SoundFont (.sf2) loading
- [ ] Search standard SoundFont locations (OS-dependent)
- [ ] Document SoundFont acquisition and setup

### More Patterns
- [ ] `ostinato(pattern)` — user-defined rhythmic patterns
- [ ] `fingerpick` — fingerstyle guitar patterns
- [ ] `latin_bass` — Latin/bossa nova bass patterns
- [ ] `breakbeat` — electronic/hip-hop drum patterns

*Note: `walking_bass`, `strum`, `alberti` moved to Phase 4. Drum patterns (`rock_beat`, `four_on_floor`, etc.) moved to Phase 2.*

### More Transforms
- [ ] `reharmonize` — chord substitution strategies
- [ ] `thin_texture` — reduce density
- [ ] `thicken_texture` — add doublings
- [ ] `rhythmic_augmentation` — double note values
- [ ] `rhythmic_diminution` — halve note values
- [ ] `retrograde` — reverse melody

### Performance Features
- [ ] Dynamics: `pp, p, mp, mf, f, ff`
- [ ] Dynamic changes: `crescendo`, `decrescendo`
- [ ] Articulation: `staccato`, `legato`, `accent`
- [ ] Tempo changes: `ritardando`, `accelerando`

### Additional Backends
- [ ] Audio rendering (FluidSynth integration)
- [ ] LilyPond export
- [ ] Ableton Live export (ALS format)
- [ ] MIDI over network (live DAW integration)

### AI Integration
- [ ] IR as LLM input/output format
- [ ] Transform suggestions based on style
- [ ] Harmonic completion
- [ ] Style transfer between pieces

### puLang Standalone Syntax
- [ ] Design complete grammar
- [ ] Implement parser
- [ ] Dedicated CLI: `pulang compile <file>`
- [ ] Dedicated CLI: `pulang play <file>`
- [ ] LSP for editor support
- [ ] File extension: `.pu` or `.pulang`

---

## What We're Explicitly NOT Doing (v1)

- ~~Notation layout (engraving)~~ — Use LilyPond/Dorico
- ~~Audio synthesis / DSP~~ — We send MIDI; use DAW/synth for sound
- ~~Video sync~~ — Use DAWs
- ~~DAW plugin~~ — Out of scope (but we support virtual MIDI ports for DAW integration)
- ~~GUI~~ — CLI/code first

These are out of scope. Other tools do them better.

---

## Success Metrics

### Phase 1-3: Does it work?
- [ ] Can compose and hear music
- [ ] Transform pipeline functions
- [ ] No major architectural issues

### Phase 4-6: Is it useful?
- [ ] Richer harmony than naive tools
- [ ] Export to real software
- [ ] Iteration is fast (<2 sec)

### Phase 7+: Do people use it?
- [ ] Real compositions created
- [ ] Feedback from other users
- [ ] Clear path to ecosystem fit

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Voice leading is hard | Phase 5 stalls | Start with simple heuristics, iterate |
| Playback latency | Poor UX | Prioritize speed in Phase 2 |
| Abstractions don't fit | Language feels awkward | Write real music early (Phase 7) |
| Scope creep | Never ships | Strict phase gating |
| Nobody cares | No users | Focus on own use first |

---

## Decision Log

*Major design decisions and their rationale.*

| Decision | Rationale |
|----------|-----------|
| Dual-syntax (pyPuLang + puLang) | Accessibility for musicians + power for programmers |
| pyPuLang first, puLang later | Iterate on semantics before committing to parser |
| Three-tier IR (Intent + Score + Event) | Score IR fills the gap between compositional intent and performance events — captures voice leading, voicing, articulation, dynamics; where music theory analysis lives |
| Dialect framework (MLIR-inspired) | Extensible IR architecture: standard dialects (Intent/Score/Event) + user-defined analytical and style dialects |
| JSON serialization for IR | Human-readable, universal, AI-friendly |
| Fractions for timing | Exact representation, no rounding errors |
| Intent IR bar-relative, Event IR piece-relative | Match mental models at each layer |
| Pitch: scientific in Intent IR, MIDI in Event IR | Human-readable vs backend-friendly |
| Roman numerals, not absolute chords | Enables transposition, modal interchange |
| `harmony()` and `progression()` as aliases | Different mental models, same semantics |
| Explicit roles, decoupled from instruments | Piano can play bass, guitar can play melody |
| Patterns as callable singletons with builders | Flexible syntax: positional, keyword, or chained |
| Duration syntax: fractions, constants, strings | Rapid prototyping, user preference |
| Transpose: key (default) and degrees (explicit) | Both musical operations are valid |
| Strict error handling | Fail fast on structural errors |
| Warn on role-based octave inference | User should know when magic happens |
| Defer Event IR to Phase 3 | Simpler Phase 1; Event IR needed for transforms, not basic emission |
| Defer Score IR to Phase 3 | Score IR is the middle layer between Intent and Event; introduced alongside Event IR when the full pipeline is built |
| Direct MIDI emission in Phase 1 | Faster path to sound; `realize_to_midi()` skips Event IR layer |
| Built-in live playback via rtmidi | Rapid prototyping requires instant feedback; file-based playback too slow |
| Layered playback: system synth → virtual port → FluidSynth | Simple default, pro DAW integration, standalone option |
| Default instruments per role | Sensible defaults for bass/harmony/melody without configuration |
| Intent IR is JSON-serializable | pyPuLang uses in-memory; standalone puLang reads/writes JSON files |
| No "IR" suffix on type names | Follow LLVM/MLIR convention; `Piece`, `Section`, not `PieceIR`, `SectionIR` |
| IR types in `pulang.ir.intent` and `pulang.ir.event` | Namespace distinguishes IR layer; types have clean names |
| No default role for tracks | Role should be explicit; warning emitted if not specified; clearer semantics |
| Track names capitalized in puLang | Helps distinguish track names from property keywords; normalized on export from pyPuLang |
| Keyword-delimited syntax (no braces) | Musicians find braces unfamiliar; ABC notation precedent; keywords sufficient for structure |
| Indentation stylistic not enforced | Recommended for readability but parser uses keywords/names for structure |
| Piece-level tracks block optional | Simple pieces can declare tracks inline in sections; complex pieces declare upfront |
| Silent tracks if not mentioned | If a track isn't used in a section, it's silent for that section |
| velocity and dynamics mutually exclusive | Can specify one or the other, not both; dynamics mapped to velocity ranges |
| Definitions with `define` block and `@` references | Reusable melodies/harmonies; `define` block + inline `as @name`; global scope |
| Variable names not case-enforced | Unlike track names, variables can be any case; `@` prefix is the disambiguator |
| Redefinition is an error | Cannot redefine a variable; explicit is better than implicit override |
| pyPuLang uses Python variables | No special `define`/`use` API; Python variables are sufficient |
| Built-in synth as default playback | Zero-config playback; no external dependencies for basic use; custom instrument control |
| Protocol-based playback backends | Extensible architecture; easy to add new backends without changing core API |
| `sounddevice` for audio output | Cross-platform, numpy integration, well-maintained, common in Python audio |
| Global config + per-call backend override | Flexible: set default once, override when needed |
| Instrument hierarchy: Instrument → Synth, SampledInstrument, Sampler | Clear separation: waveform synth (Phase 2), bundled samples (future), user samples (future) |
| InstrumentBank for instrument assignment | Supports both role-based and track-name-based assignment |
| Bundled samples: one-shot, multi-velocity, OGG format | Good quality/size tradeoff (~5-10 MB); deferred to future phase |
| FluidSynth as optional backend | Pro-quality sounds via SoundFonts; deferred to future phase |
| Drums as regular tracks with `Role.RHYTHM` | Minimal new API; consistent with existing track/pattern system |
| GM drum map constants (`KICK`, `SNARE`, etc.) | More readable than MIDI numbers; standard mapping |
| Optional grid notation for drums | "x...x..." syntax is familiar and readable for polyrhythms |
| Auto-assign MIDI channel 10 for rhythm role | GM standard; transparent to user |
| `walking_bass`, `strum` in Phase 4 | Require richer harmony context (extended chords, inversions) |
