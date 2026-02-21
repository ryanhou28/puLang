# puLang Review Notes (Initial Assessment)

*Rough sketch capturing initial analysis before formal documentation.*

---

## 1. Positioning Assessment

### Strengths
- "Gap #2" framing is accurate — no rapid, programmable composition language at harmonic/structural intent level
- Comparison table is honest, not overselling
- "Compiler passes for music" angle is genuinely novel and underserved

### Concerns
- Positioning conflates two different users:
  - **Composer-programmers** — want expressiveness and speed
  - **AI/ML researchers** — want predictability and serialization
- These have different needs; must decide who's primary

**Recommendation:** Lead with composer-programmers. If the language feels good to compose with, AI researchers will adopt it. The reverse is not true.

---

## 2. Demand Assessment

### Real Demand Signals
- music21 has ~3k GitHub stars but terrible generation ergonomics
- TidalCycles has devoted community but weak harmony support
- AI music papers keep inventing ad-hoc representations
- LLM + music is exploding, but no good "source format"

### Demand Risks
- Composers who code are a small population
- Most composers prefer GUIs (DAWs, notation software)
- "Rapid prototyping" value prop requires iteration loop to be *very* fast
- If compile-and-hear takes >2 seconds, people will just use a piano roll

**Assessment:** Demand exists but is niche. That's fine — compilers, Vim, and Haskell are niche too. But must nail the core experience for that niche.

---

## 3. Feasibility Assessment

### Straightforward
- Python embedding with DSL — well-understood pattern
- Lowering to MIDI — solved problem
- Basic harmony/pattern constructs — not algorithmically hard

### Hard
- **Voice leading transforms** — real algorithmic challenge (constraint satisfaction, heuristics)
- **Rhythm generation that sounds musical** — harder than it seems
- **Making the IR actually useful** — easy to over-engineer, hard to get right abstractions
- **Playback latency** — Python + MIDI playback can be sluggish

**Verdict:** Very doable as prototype. Question is whether abstractions survive contact with real compositions.

---

## 4. Best Usage / Target Workflow

The clearest use case:
```
Sketch harmonic structure → Generate pattern variations → Audition → Refine → Export
```

**NOT:**
- Final production (DAW's job)
- Performance (Tidal/SuperCollider)
- Engraving (LilyPond/Dorico)

**puLang's sweet spot:** The 10 minutes before you open your DAW, where you're figuring out what the piece *is*.

---

## 5. Language Design Assessment

### What Works
- `section`, `harmony`, `pattern` as core primitives — good granularity
- `with piece(...)` context manager syntax — Pythonic, readable
- Transform-as-method pattern (`verse.transform(...)`) — composer-friendly

### Concerns

#### a) The "escape hatch" problem
Literal notes "allowed but discouraged" — but every composer will hit moments where they need specific notes.
- If escape hatch is awkward → they abandon the language
- If too easy → nobody uses abstractions

**Recommendation:** Design escape hatch carefully:
```python
verse.track("melody").notes([D4, F4, A4], at=beat(3))  # explicit, but not ugly
```

#### b) The rhythm representation problem
Underspecified. `rate=1/16` is fine for arpeggios, but how to express:
- Syncopation?
- Swing?
- Rubato?
- Polyrhythm?

This is where most music DSLs get messy.

#### c) The harmony → notes gap (Addressed in v0.2)
`I, V, vi, IV` is great, but *which* voicing? *Which* octave? *Which* inversion?

**Resolution:** Score IR explicitly captures these decisions. The Intent → Score lowering makes voicing and voice leading choices, and Score IR preserves them as inspectable, analyzable, transformable data. Users can:
- Inspect Score IR to see exactly which voicings were chosen
- Apply score-level passes to optimize voice leading
- Configure lowering style (default, jazz, baroque) for different voicing conventions
- Override with explicit voicing hints (`I.open()`, `V.close()`, etc.)

---

## 6. Architecture Assessment

### What's Correct
IR-centric architecture separating:
- Frontends (pyPuLang Python DSL + puLang standalone syntax)
- IR (three-tier: Intent IR, Score IR, Event IR)
- Passes (analysis + transform at each level)
- Backends (MIDI, MusicXML, audio)

This enables transform passes that make the language interesting.

### Resolved: IR Granularity (v0.2 Update)

Originally recommended two tiers (Intent + Event). In v0.2, we moved to **three tiers** (Intent + Score + Event) because the gap between intent and events was too large. Score IR fills the middle layer where music theory analysis lives — voice leading, voicing, counterpoint, articulation, dynamics.

The architecture is now built on an **MLIR-inspired dialect framework**: the three standard dialects (Intent, Score, Event) provide the core compilation path, but the framework supports user-defined dialects for specialized analysis (Schenkerian, set theory, counterpoint) and style-specific conventions (jazz voicings, Baroque ornaments).

See [ir-spec.md](ir-spec.md) for the full dialect framework specification.

### Partially Resolved: Transform pass ordering
Compiler passes have dependencies. In v0.2, passes naturally partition by IR level:
1. Intent-level passes (harmonic transforms) run first
2. Lowering to Score (voicing, voice leading decisions)
3. Score-level passes (voice leading optimization, ornamentation)
4. Lowering to Event (performance interpretation)
5. Event-level passes (humanize, swing)

Within a single level, ordering is still explicit (user-specified). Dependency-based ordering is a future enhancement.

---

## 7. Music IR Compatibility

### Keep Compatible
- Keep IR serializable (JSON/protobuf/etc.)
- Keep constructs semantically clear (a `Chord` should mean a chord, not "some notes")
- Avoid puLang-specific constructs in IR — IR should be language-agnostic
- Dialect framework should be open — third-party dialects should be first-class

### Addressed in v0.2
- Score IR provides a natural bridge to MusicXML and music21 (both operate at roughly the same level)
- Dialect framework provides extensibility without modifying core

### Defer
- Multi-instrument orchestration semantics
- Audio-level representation
- Notation-level representation (layout, beaming — Score IR is *moderate* granularity, not a notation format)

---

## 8. Critical Risks

1. **Abstraction mismatch** — If puLang's abstractions don't match how composers think, they'll fight the language
2. **Iteration latency** — If hearing changes takes >1-2 seconds, tool loses its value
3. **Scope creep** — Temptation to add notation, DSP, live coding will kill focus
4. **IR over-engineering** — Easy to design beautiful IR nobody can emit or consume

---

## 9. Amended Plan

Original proposal:
> Define 3 core constructs → Lower to IR → Emit MIDI → One transform pass

Amended to:

1. **Define 5 core constructs:** `piece`, `section`, `harmony`, `track`, `pattern`
2. **Lower to ONE IR dialect first** (Event IR — the concrete notes)
3. **Emit MIDI that you can hear in <1 second**
4. **Demonstrate one transform** that modifies IR before emission
5. **Write 3 real compositions** in pyPuLang to stress-test the design

The "3 real compositions" step is critical. If you can't write music you'd actually want to hear, the language failed.

---

## 10. Documents to Draft

| Document | Purpose |
|----------|---------|
| `positioning.md` | What puLang is / isn't |
| `architecture.md` | IR layers, transform pipeline |
| `language-spec.md` | Core constructs, syntax, semantics |
| `ir-spec.md` | IR format (start minimal) |
| `roadmap.md` | Phased plan, what's deferred |

---

## Overall Take

**The idea is sound.** The gap is real, the positioning is clear, and the IR-centric architecture is correct.

**The risks are execution risks**, not concept risks:
- Can you make it fast enough to feel interactive?
- Can you make the abstractions match composer intuition?
- Can you resist scope creep?

**Recommendation:** Start with absolute minimum that lets you compose a 16-bar piece, hear it, and apply one transform. That's the proof of concept. Everything else is premature.
