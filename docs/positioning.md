# puLang Positioning

## One-Sentence Definition

**puLang is an intent-first music composition language that lowers into a Music IR, enabling rapid musical prototyping, structured transformations, and multi-target rendering.**

---

## Two Syntaxes, One Language

puLang has two surface syntaxes that share the same semantics and IR:

| Syntax | Name | Description | Target Users |
|--------|------|-------------|--------------|
| **pyPuLang** | Python-embedded DSL | Method chaining, context managers | Programmers, AI/ML researchers |
| **puLang** | Standalone syntax | Music-native, sheet-music-like | Musicians, composers |

Both syntaxes:
- Lower to the same Intent IR
- Share the same transform pipeline
- Emit to the same backends

**Development approach:** We design both syntaxes together from the start to ensure semantic alignment, but implement pyPuLang first. The standalone puLang syntax will be implemented once pyPuLang stabilizes.

### pyPuLang (Python-embedded)

```python
from pulang import *

with piece(tempo=120, key="C major") as p:
    verse = p.section("verse", bars=8)
    verse.harmony(I, IV, vi, V)
    verse.track("bass").pattern(root_eighths).octave(-2)
```

### puLang (Standalone — Future)

```
piece "My Song" tempo=120 key=C:

  Verse [8 bars]:
    harmony: I  IV  vi  V

    Bass:
      pattern: root_eighths
      octave: -2
```

The standalone syntax is designed to be accessible to musicians who may not know Python, while the Python syntax provides full programmatic power.

---

## The Gap puLang Fills

### What Exists Today

| Tool | Operates At | Strength | Weakness |
|------|-------------|----------|----------|
| DAWs | Notes, audio | Fast playback, production | No abstraction, no refactoring |
| LilyPond | Notation | Precise engraving | Slow iteration, note-level |
| music21 | Notes, analysis | Strong analysis | Awkward generation |
| Alda | Notes | Text-based | Still note-centric |
| TidalCycles | Patterns | Temporal algebra | Weak harmony, no notation |
| SuperCollider | DSP + patterns | Powerful synthesis | Not composition-first |

### What's Missing

No tool lets composers:
- Express **harmonic intent** rather than specific notes
- Express **textural intent** rather than explicit voicings
- Express **structural patterns** that generate notes
- Apply **compiler-like transforms** to musical material
- **Refactor** a composition like refactoring code

This is Gap #2: **No rapid, programmable composition language.**

---

## What puLang Is

### Core Identity

puLang is:
- **A composition language** — for sketching musical ideas
- **Intent-first** — you declare what you want, not every note
- **IR-centric** — lowers to intermediate representations that can be transformed
- **Dual-syntax** — Python-embedded (pyPuLang) and standalone (puLang)
- **Transform-friendly** — musical material can be analyzed and modified programmatically

### Primary Granularity

puLang operates at:
- **Sections** — formal units of a piece
- **Harmony** — chord progressions, key areas, modulations
- **Patterns** — rhythmic/melodic generators (arpeggios, ostinatos, etc.)
- **Tracks/Roles** — instrument parts with musical function
- **Transforms** — operations that modify musical material

### Secondary Granularity (Escape Hatch)

When needed, puLang allows:
- Literal notes
- Explicit timing
- Explicit voicing

These are available but not the primary mode of expression.

---

## What puLang Is Not

### Not a DAW Replacement
puLang is for the 10 minutes *before* you open your DAW — figuring out what the piece is. Production happens elsewhere.

### Not a Notation System
puLang can emit to notation formats, but it's not a layout engine. LilyPond, Dorico, and Finale handle engraving.

### Not a Performance Language
puLang is score-driven, not performance-driven. TidalCycles and SuperCollider handle live coding and real-time DSP.

### Not a Universal Music Format
puLang is a *source* format for composition. It doesn't try to represent all possible musical information.

### Not an Audio/DSP Environment
puLang emits symbolic music (MIDI, MusicXML). Synthesis and audio processing happen downstream.

---

## Target Users

### Primary: Composer-Programmers
Musicians who:
- Think in harmonic and structural terms
- Want to iterate faster than DAWs allow
- Are comfortable with code
- Want to explore variations programmatically

### Secondary: AI/ML Researchers
Researchers who:
- Need a controllable music representation
- Want human-editable intermediate formats
- Are building hybrid human/AI composition tools

### Tertiary: Music Technologists
Developers building:
- Algorithmic composition tools
- Music education software
- Generative music systems

---

## Target Workflow

```
Idea → Intent (puLang) → IR → Transforms → Audition → Refine → Export
```

Compared to traditional:
```
Idea → Notes → Performance → Rewrite → Frustration
```

The key difference: **you can refactor, transform, and iterate at the intent level** before committing to specific notes.

---

## Differentiation

### vs music21
- music21 is a **library**; puLang is a **language**
- music21 is for **analysis**; puLang is for **generation**
- music21 operates on notes; puLang operates on intent

### vs LilyPond
- LilyPond is for **final engraving**; puLang is for **pre-engraving exploration**
- LilyPond is about **correctness**; puLang is about **iteration**
- LilyPond is note-level; puLang is intent-level

### vs TidalCycles
- Tidal is **temporal pattern algebra**; puLang is **harmonic + structural composition**
- Tidal is **performance-driven**; puLang is **score-driven**
- Tidal is weak on harmony; puLang centers harmony

### vs Alda
- Alda is still **note-centric**
- puLang adds **intent layer** and **transform pipeline**

---

## The Killer Feature: Transformability

Because puLang lowers to IR, you can apply transforms:

```python
chorus = verse.transform(
    reharmonize="modal_interchange",
    density=1.3,
    register=+1
)
```

```python
piece.apply(
    voice_leading(max_leap=5),
    thin_texture(except_role="melody")
)
```

These are **compiler passes**, not ad-hoc scripts. This is the door no existing tool opens.

---

## Success Criteria

puLang succeeds if:
1. You can compose a piece faster than in a DAW
2. You can hear your changes in <2 seconds
3. You can apply a transform and get musically sensible results
4. The abstractions match how you think about music
5. You'd actually use it for real compositions

puLang fails if:
1. You fight the language to express what you want
2. The iteration loop is too slow
3. The transforms produce garbage
4. You always escape to literal notes
5. It's a cool demo but not a usable tool
