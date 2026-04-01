# puLang Compiler Roadmap

This document outlines the roadmap for implementing the standalone puLang compiler frontend (.pu file parser/compiler).

## Overview

The puLang compiler frontend parses `.pu` source files and lowers them to the same Intent IR used by pyPuLang, enabling both syntaxes to share the same backend pipeline.

```
.pu file → Parser → Intent IR (JSON) → (same pipeline as pyPuLang)
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  puLang Source (.pu file)                               │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Lark Parser (grammar.lark)                             │
│  - Lexer: tokenize                                      │
│  - Parser: build parse tree                             │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Parse Tree (Lark Tree object)                          │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Transformer (lark.Transformer subclass)                │
│  - Walk parse tree                                      │
│  - Resolve symbols                                      │
│  - Validate semantics                                   │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Intent IR (pulang.ir.intent.Piece)                     │
│  - Same IR as pyPuLang                                  │
│  - JSON-serializable                                    │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Parser | Lark (Earley) | Indentation support, concise grammar, good error messages |
| CLI | Click | Clean API, auto-generated help text |
| Testing | pytest | Standard Python testing framework |
| File watching | watchdog | Cross-platform file monitoring |
| Serialization | dataclasses + json | Simple, built-in, no extra dependencies |
| Error reporting | Click + colorama (optional) | Clear error output |

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Single package | Unified `pulang` package | Simpler dependency management, easier co-evolution |
| CLI default | `pulang compile` for compilation | Clear intent, separate play command available |
| Error messages | Basic in Phase 1, improve later | Ship quickly, iterate on UX |
| Validation strictness | Tiered (errors/warnings/lints) | Balance strictness with flexibility |
| JSON IR format | Direct dataclass serialization | Round-trip correctness, easy deserialization |
| Multi-file support | Defer to Phase 3 | Single-file sufficient for Phase 1-2 |
| Intermediate caching | No caching in Phase 1 | Keep it simple, add if needed |
| MIDI testing | Structural correctness only | Byte-by-byte is fragile and unnecessary |
| Feature scope | Minimal subset first | Ship working compiler, expand incrementally |
| Interactive mode | Use Python REPL with pypulang | No need for puLang-specific REPL |

---

## Phase 1: Minimal Working Compiler

**Goal:** Parse a minimal .pu file and emit MIDI.

**Scope:**
- Single section
- Basic harmony (I, IV, V, etc.)
- Single track with pattern
- No escape hatch (literal notes)
- No definitions/variables
- No transforms

### 1.1 Project Setup

- [ ] Create `pulang/frontend/` directory
- [ ] Add Lark dependency: `lark>=1.1.0`
- [ ] Add Click dependency for CLI: `click>=8.0.0`
- [ ] Update `pyproject.toml` with new dependencies
- [ ] Create `pulang/frontend/__init__.py`

### 1.2 Minimal Grammar (Lark)

**File:** `pulang/frontend/grammar.lark`

**Minimal example that should parse:**
```
piece "Test" tempo=120 key=C

section Verse [4 bars]:
  harmony: I IV V I

  Bass:
    role: bass
    pattern: root_quarters
    octave: -1
```

**Tasks:**
- [ ] Define tokens: STRING, NAME, NUMBER, keywords
- [ ] Define `piece` rule: `piece STRING piece_attrs*`
- [ ] Define `piece_attrs`: `tempo`, `key`, `time`
- [ ] Define `section` rule: `section NAME "[" NUMBER "bars" "]" ":"`
- [ ] Define `harmony` rule: `harmony ":" chord+`
- [ ] Define `chord` rule: roman numerals (I-VII, i-vii)
- [ ] Define `track_block` rule: `NAME ":" track_stmt+`
- [ ] Define `track_stmt`: `pattern`, `octave`, `role`
- [ ] Add indentation handling: `%declare _INDENT _DEDENT`
- [ ] Test: parse minimal example without crashes

### 1.3 Parse Tree → Intent IR (Transformer)

**File:** `pulang/frontend/transformer.py`

- [ ] Create `PuLangTransformer(lark.Transformer)` class
- [ ] Implement `piece()` method → `ir.intent.Piece`
- [ ] Implement `section()` method → `ir.intent.Section`
- [ ] Implement `harmony()` method → `ir.intent.Harmony`
- [ ] Implement `chord()` method → `ir.intent.Chord`
- [ ] Implement `track_block()` method → `ir.intent.Track`
- [ ] Implement `piece_attrs` parsing (tempo, key, time_sig)
- [ ] Implement pattern name → `Pattern` object mapping
- [ ] Handle octave_shift, velocity, role assignment
- [ ] Test: transformer produces valid Intent IR

### 1.4 Compiler Entry Point

**File:** `pulang/frontend/compiler.py`

```python
def compile_pulang(source: str, filename: str = "<string>") -> Piece:
    """Compile .pu source to Intent IR."""
    parser = Lark.open("grammar.lark", rel_to=__file__, parser="earley")

    try:
        tree = parser.parse(source)
    except lark.exceptions.LarkError as e:
        raise CompileError(f"Syntax error: {e}")

    transformer = PuLangTransformer()

    try:
        piece_ir = transformer.transform(tree)
    except Exception as e:
        raise CompileError(f"Semantic error: {e}")

    return piece_ir

def compile_file(path: Path) -> Piece:
    """Compile .pu file to Intent IR."""
    with open(path) as f:
        source = f.read()
    return compile_pulang(source, filename=str(path))
```

**Tasks:**
- [ ] Implement `compile_pulang(source: str) -> Piece`
- [ ] Implement `compile_file(path: Path) -> Piece`
- [ ] Implement `CompileError` exception class
- [ ] Add line/column info to error messages (from Lark)
- [ ] Test: end-to-end compilation

### 1.5 CLI Commands

**File:** `pulang/cli.py`

**Commands to implement:**

```bash
# Compilation
pulang compile song.pu              # → song.mid (default)
pulang compile song.pu -o out.mid   # → custom output
pulang compile song.pu --json       # → song.json (IR output)

# Playback
pulang play song.pu                 # Parse and play immediately
pulang play song.pu --loop          # Loop playback
pulang play song.pu --section=verse # Play specific section

# Utilities
pulang check song.pu                # Parse and validate (no output)
pulang show song.pu                 # Pretty-print IR as JSON
```

**Implementation sketch:**
```python
import click
from pulang.frontend.compiler import compile_file
from pulang.backend.midi import emit_midi

@click.group()
def cli():
    """puLang compiler and tools."""
    pass

@cli.command()
@click.argument('input', type=click.Path(exists=True))
@click.option('-o', '--output', help='Output file path')
@click.option('--json', is_flag=True, help='Output IR as JSON')
def compile(input, output, json):
    """Compile .pu file to MIDI."""
    piece = compile_file(Path(input))

    if json:
        output = output or Path(input).with_suffix('.json')
        with open(output, 'w') as f:
            f.write(piece.to_json())
    else:
        output = output or Path(input).with_suffix('.mid')
        midi = emit_midi(piece)
        midi.save(output)

    click.echo(f"Compiled: {output}")

@cli.command()
@click.argument('input', type=click.Path(exists=True))
@click.option('--loop', is_flag=True, help='Loop playback')
@click.option('--section', help='Play specific section')
def play(input, loop, section):
    """Parse and play .pu file."""
    piece = compile_file(Path(input))

    if section:
        piece.play(section=section)
    elif loop:
        piece.loop()
    else:
        piece.play()

@cli.command()
@click.argument('input', type=click.Path(exists=True))
def check(input):
    """Validate .pu file without output."""
    try:
        piece = compile_file(Path(input))
        click.echo(f"✓ {input} is valid")
    except CompileError as e:
        click.echo(f"✗ {input}: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.argument('input', type=click.Path(exists=True))
def show(input):
    """Pretty-print IR as JSON."""
    piece = compile_file(Path(input))
    click.echo(piece.to_json(indent=2))

if __name__ == '__main__':
    cli()
```

**Tasks:**
- [ ] Implement `pulang compile <file>` command
- [ ] Implement `pulang compile <file> -o output.mid`
- [ ] Implement `pulang compile <file> --json` (emit IR)
- [ ] Implement `pulang play <file>` command
- [ ] Implement `pulang play <file> --loop`
- [ ] Implement `pulang play <file> --section=name`
- [ ] Implement `pulang check <file>` (validate only)
- [ ] Implement `pulang show <file>` (pretty-print IR)
- [ ] Add `--help` text for all commands
- [ ] Test: all CLI commands work

### 1.6 Entry Point Setup

**File:** `pyproject.toml`

```toml
[project.scripts]
pulang = "pulang.cli:cli"
```

**Tasks:**
- [ ] Add CLI entry point to `pyproject.toml`
- [ ] Test: `pulang --help` works after install
- [ ] Test: `pulang compile examples/test.pu` works

### 1.7 Semantic Validation (Basic)

**File:** `pulang/frontend/validator.py`

**Validation levels:**
```python
class ValidationLevel(Enum):
    ERROR = "error"      # Invalid IR, won't compile
    WARNING = "warning"  # Legal but suspicious
    LINT = "lint"        # Style/convention issue
```

**Validations to implement:**

**Errors (must fix):**
- Harmony duration doesn't match section bars
- Pattern doesn't exist in registry
- Variable referenced but not defined

**Warnings (should fix):**
- Track has no role
- Track declared but never has content
- Octave shift puts bass above melody range

**Implementation sketch:**
```python
class ValidationError(CompileError):
    """Semantic validation error."""
    pass

def validate(piece: Piece) -> list[str]:
    """Validate Intent IR, return warnings."""
    warnings = []

    for section in piece.sections:
        # Error: harmony duration must match section bars
        harmony_duration = section.harmony.total_duration()
        section_duration = section.bars * section.time_signature.bar_duration()
        if harmony_duration != section_duration:
            raise ValidationError(
                f"Section '{section.name}': harmony is {harmony_duration} beats "
                f"but section is {section_duration} beats"
            )

        # Warning: track has no role
        for track in section.tracks:
            if track.role is None:
                warnings.append(
                    f"Section '{section.name}', track '{track.name}': "
                    f"no role specified"
                )

    return warnings
```

**Tasks:**
- [ ] Implement `validate(piece: Piece) -> list[str]` function
- [ ] Error: harmony duration doesn't match section bars
- [ ] Error: pattern doesn't exist in registry
- [ ] Warning: track has no role
- [ ] Warning: track declared but never has content
- [ ] Integrate validation into compiler pipeline
- [ ] Test: validation catches common errors

### 1.8 IR JSON Serialization

**File:** Update `pulang/ir/intent.py`

```python
from dataclasses import dataclass, asdict
import json
from fractions import Fraction

def _default_serializer(obj):
    """Custom serializer for non-standard types."""
    if isinstance(obj, Fraction):
        return str(obj)  # "3/4"
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

@dataclass
class Piece:
    # ... existing fields ...

    def to_json(self, indent=None) -> str:
        """Serialize to JSON."""
        return json.dumps(
            asdict(self),
            indent=indent,
            default=_default_serializer
        )

    @classmethod
    def from_json(cls, json_str: str) -> 'Piece':
        """Deserialize from JSON."""
        data = json.loads(json_str)
        # TODO: proper deserialization with type handling
        # Convert string fractions back to Fraction objects
        # Convert enum values back to enums
        return cls(**data)
```

**Tasks:**
- [ ] Implement `Piece.to_json()` method
- [ ] Implement `Piece.from_json()` classmethod
- [ ] Handle `Fraction` serialization (convert to string "3/4")
- [ ] Handle enum serialization (Role, etc.)
- [ ] Test: roundtrip works (IR → JSON → IR)

### 1.9 Test Suite

**Directory:** `tests/frontend/`

**Test categories:**

1. **Grammar tests** (parse validity)
```python
def test_parse_basic_piece():
    source = """
    piece "Test" tempo=120 key=C

    section Verse [4 bars]:
      harmony: I IV V I
    """
    tree = parser.parse(source)
    assert tree is not None
```

2. **Semantic tests** (valid IR generation)
```python
def test_harmony_duration_matches_bars():
    source = """..."""
    ir = compile_pulang(source)
    assert ir.sections[0].harmony.total_duration() == 4
```

3. **Roundtrip tests** (IR → JSON → IR)
```python
def test_ir_json_roundtrip():
    ir1 = compile_pulang(source)
    json_str = ir1.to_json()
    ir2 = Piece.from_json(json_str)
    assert ir1 == ir2
```

4. **Structural MIDI tests** (.pu → .mid output)
```python
def test_compile_to_midi():
    midi = compile_to_midi("examples/example1.pu")

    # Check structural properties
    assert midi.tempo == 120
    assert len(midi.tracks) == 2
    assert midi.tracks[0].name == "Bass"

    # Check note events
    notes = [msg for msg in midi.tracks[0] if msg.type == 'note_on']
    assert notes[0].note == 48  # C3
    assert notes[0].velocity > 0
```

5. **Error tests** (validation)
```python
def test_undefined_track_error():
    source = """
    section Verse:
      Bass:
        pattern: root_quarters  # Bass never declared
    """
    with pytest.raises(CompileError, match="Track 'Bass' not declared"):
        compile_pulang(source)
```

**Tasks:**
- [ ] Test grammar: parse valid .pu files
- [ ] Test grammar: reject invalid syntax
- [ ] Test transformer: produces correct IR
- [ ] Test compiler: end-to-end .pu → IR
- [ ] Test validation: catches semantic errors
- [ ] Test CLI: all commands produce expected output
- [ ] Test roundtrip: IR → JSON → IR
- [ ] Test MIDI output: structural correctness
- [ ] Create 5 example .pu files in `examples/`
- [ ] Achieve >80% test coverage for frontend code

### 1.10 Documentation

- [ ] Update main README with puLang compiler section
- [ ] Write `docs/pulang-compiler-usage.md` (CLI usage guide)
- [ ] Write `docs/pulang-tutorial.md` (hello world → simple song)
- [ ] Document CLI commands with examples
- [ ] Add grammar railroad diagram (use Lark's tooling or manual)
- [ ] Add 5 example .pu files with comments in `examples/pulang/`

### Exit Criteria (Phase 1)

- [ ] Can compile minimal .pu file to MIDI
- [ ] Can play .pu file directly with `pulang play`
- [ ] Validation catches harmony/section mismatch
- [ ] All CLI commands work and have `--help` text
- [ ] At least 5 working example files
- [ ] Test coverage >80% for frontend code
- [ ] Documentation covers basic usage

---

## Phase 2: Feature Completeness

**Goal:** Match pypulang feature set for .pu syntax.

### 2.1 Multiple Sections

```
section Verse [8 bars]:
  harmony: I IV V I

section Chorus [8 bars]:
  harmony: IV V I vi
```

**Tasks:**
- [ ] Update grammar: allow multiple `section` blocks
- [ ] Update transformer: handle section list
- [ ] Test: piece with verse + chorus compiles

### 2.2 Track Declaration Block

```
tracks
  Bass [role=bass]
  Keys [role=harmony]

section Verse [8 bars]:
  harmony: I IV V

  Bass:
    pattern: root_quarters

  Keys:
    pattern: block_chords
```

**Tasks:**
- [ ] Add `tracks` block to grammar
- [ ] Parse track declarations with attributes
- [ ] Validate: tracks used in sections must be declared
- [ ] Warning: tracks declared but never used
- [ ] Test: track declaration system works

### 2.3 Escape Hatch (Literal Notes)

```
Melody:
  notes: C4/4 D4/4 E4/2 | G4/4 rest/4 F4/2
```

**Tasks:**
- [ ] Add `notes` syntax to grammar
- [ ] Parse pitch literals: `C4`, `Db5`, `Cs5`, etc.
- [ ] Parse duration: `/4`, `/8`, `/16`, `/2`, etc.
- [ ] Parse `rest` keyword
- [ ] Support `|` as bar separator (optional, cosmetic)
- [ ] Transform to `ir.intent.Notes` dataclass
- [ ] Test: literal notes compile correctly

### 2.4 Chord Extensions

```
harmony: Imaj7 V7 vi9 ii7 IVsus4
```

**Tasks:**
- [ ] Add chord extensions to grammar: `7`, `9`, `maj7`, `min7`, etc.
- [ ] Add suspended chords: `sus2`, `sus4`
- [ ] Add diminished/augmented: `dim`, `aug`, `°`, `+`
- [ ] Update transformer to parse extensions
- [ ] Test: extended chords resolve correctly

### 2.5 Inversions

```
harmony: I I/1 I/2  # Root position, 1st inversion, 2nd inversion
```

**Tasks:**
- [ ] Add inversion syntax: `I/1`, `I/2`
- [ ] Update transformer to parse inversions
- [ ] Test: inversions produce correct bass notes

### 2.6 Definitions and Variables

```
define
  @verse_harmony as
    I IV vi V

  @verse_melody as
    C4/4 D4/4 E4/2

section Verse [8 bars]:
  harmony: @verse_harmony

  Melody:
    notes: @verse_melody
```

**Tasks:**
- [ ] Add `define` block to grammar
- [ ] Parse variable definitions: `@name as ...`
- [ ] Parse variable references: `@name`
- [ ] Implement symbol table in transformer
- [ ] Validate: undefined variables raise error
- [ ] Validate: redefinition raises error
- [ ] Test: definitions and references work

### 2.7 Chord Duration Syntax

```
harmony: (I, 2) (IV, 1) (V, 1)  # I for 2 bars, IV and V for 1 bar each
```

**Tasks:**
- [ ] Add tuple syntax for chord duration
- [ ] Update transformer to handle explicit durations
- [ ] Mix explicit/implicit durations in same harmony line
- [ ] Test: mixed explicit/implicit durations work

### 2.8 Secondary Dominants

```
harmony: I V/V V I  # V/V = V of V
harmony: ii V/vi vi V
```

**Tasks:**
- [ ] Add secondary dominant syntax: `V/ii`, `V/V`, `V/vi`, etc.
- [ ] Update transformer to parse secondary dominants
- [ ] Test: secondary dominants resolve correctly

### 2.9 Advanced Rhythmic Patterns

```
Bass:
  pattern: walking_bass(approach=chromatic)

Guitar:
  pattern: strum("D.DU.UDU")
```

**Tasks:**
- [ ] Add pattern parameters to grammar
- [ ] Parse pattern calls: `name(param=value)`
- [ ] Support string parameters for grid patterns
- [ ] Support keyword arguments
- [ ] Ensure rhythm edge cases (tuplets, metric modulation) can be expressed
- [ ] Test: parametric patterns work

### 2.10 Instruments in puLang

```
tracks
  Bass [role=bass, instrument=Synth(waveform=saw, cutoff=400)]

# Or simpler:
tracks
  Bass [role=bass, synth=saw]
```

**Tasks:**
- [ ] Add `instrument` attribute to track declarations
- [ ] Parse instrument specs (simplified syntax)
- [ ] Map to `Synth` / `DrumSampler` / etc.
- [ ] Support simplified syntax: `synth=saw` → `Synth(waveform="saw")`
- [ ] Test: custom instruments apply correctly

### 2.11 Watch Mode

```bash
pulang watch song.pu  # Recompile + play on file change
```

**Tasks:**
- [ ] Add `watchdog` dependency
- [ ] Add `pulang watch <file>` command
- [ ] Use `watchdog` library for file monitoring
- [ ] Recompile on .pu file change
- [ ] Restart playback automatically (stop previous, start new)
- [ ] Add debouncing (avoid recompiling on rapid saves)
- [ ] Test: watch mode detects changes

### Exit Criteria (Phase 2)

- [ ] Feature parity with pypulang DSL
- [ ] All pypulang example compositions have .pu equivalents
- [ ] Can express literal notes, definitions, multi-section pieces
- [ ] Watch mode works for rapid iteration
- [ ] Documentation updated with all new features

---

## Phase 3: Advanced Features

**Goal:** Polish, multi-file support, better tooling.

### 3.1 Multi-File Support

```
# library.pu
define
  @jazz_progression as
    IVmaj7 V7/V V7 I

# song.pu
import library

section Bridge:
  harmony: @jazz_progression
```

**Tasks:**
- [ ] Add `import` statement to grammar
- [ ] Implement file resolution (relative paths, search paths)
- [ ] Implement cross-file symbol resolution
- [ ] Validate: cyclic imports raise error
- [ ] Validate: imported file not found raises clear error
- [ ] Support `import library as lib` (namespacing)
- [ ] Test: multi-file projects compile

### 3.2 Init Command

```bash
$ pulang init my-song
Created: my-song/
  my-song.pu
  README.md
```

**Tasks:**
- [ ] Implement `pulang init <name>` command
- [ ] Create template .pu file with example structure
- [ ] Create README with basic instructions
- [ ] Add `--template` option for different templates (pop, jazz, classical)
- [ ] Test: init creates valid, compilable project

### 3.3 Format Command

```bash
$ pulang fmt song.pu  # Auto-format/pretty-print
$ pulang fmt song.pu --check  # Check if formatted (CI mode)
```

**Tasks:**
- [ ] Implement canonical .pu formatter
- [ ] Normalize indentation (2 spaces)
- [ ] Normalize spacing around operators
- [ ] Normalize blank lines between sections
- [ ] Add `--check` flag (CI mode, exit 1 if unformatted)
- [ ] Add `--diff` flag (show changes without applying)
- [ ] Test: formatter produces valid, idiomatic .pu files

### 3.4 Error Message Improvements

**Goal:** Rust-level error quality

```
Error: Invalid harmony duration
  --> song.pu:5:3
   |
 5 |   harmony: I IV vi V
   |   ^^^^^^^^^^^^^^^^^ Only 4 beats, but section is 8 bars
   |
Help: Each chord defaults to 1 bar. Did you mean:
    harmony: (I, 2) (IV, 2) (vi, 2) (V, 2)
```

**Tasks:**
- [ ] Add "did you mean?" suggestions for typos (using Levenshtein distance)
- [ ] Add color-coded error output (use `click.style` or `rich` library)
- [ ] Add context snippets (show 3 lines around error with line numbers)
- [ ] Add hints for common mistakes
- [ ] Add "help" sections with suggested fixes
- [ ] Test: error messages are helpful and actionable

### 3.5 Improved Validation

**Additional validations:**
- [ ] Warn: section has no tracks (silent section)
- [ ] Warn: track assigned to incompatible role (e.g., drums with harmony pattern)
- [ ] Error: invalid octave shift (would produce out-of-range MIDI notes)
- [ ] Lint: track names not capitalized (puLang convention)
- [ ] Lint: inconsistent indentation
- [ ] Add `--strict` flag to treat warnings as errors

### Exit Criteria (Phase 3)

- [ ] Multi-file projects work seamlessly
- [ ] `pulang init` helps new users get started
- [ ] `pulang fmt` produces consistently formatted code
- [ ] Error messages are excellent (clear, actionable, helpful)
- [ ] Validation catches common mistakes early

---

## Phase 4: Transforms and Event IR Output

**Goal:** Integrate the transform pipeline and stabilize lower-level Event IR emission from the compiler frontend.

### 4.1 CLI Output Formats
- [ ] Add `--ir=intent` and `--ir=score` flags to `pulang compile`
- [ ] Integrate Intent -> Score -> Event lowering correctly into CLI
- [ ] Test: Correct IR level is output when requested

### 4.2 Escape Hatch Locking
- [ ] Add syntax for locking literal notes from transformations
- [ ] Parse and lower `locked=True` property on Notes objects
- [ ] Validate locking semantics in transformations

---

## Phase 5: Tooling & Ecosystem

**Goal:** IDE support, language server, VSCode extension.

### 5.1 Language Server Protocol (LSP)

**Features to implement:**
- Diagnostics (errors/warnings in real-time)
- Hover info (show chord notes, pattern documentation)
- Completion (chord numerals, pattern names, track names)
- Go to definition (for variables, tracks)
- Document symbols (outline view)
- Formatting (integrate `pulang fmt`)

**Tasks:**
- [ ] Add `pygls` dependency (Python LSP framework)
- [ ] Implement basic LSP server
- [ ] Support `textDocument/publishDiagnostics` (errors/warnings)
- [ ] Support `textDocument/hover` (show chord info, pattern docs)
- [ ] Support `textDocument/completion` (chord numerals, pattern names)
- [ ] Support `textDocument/definition` (goto definition for variables)
- [ ] Support `textDocument/documentSymbol` (outline)
- [ ] Support `textDocument/formatting` (call `pulang fmt`)
- [ ] Add `pulang lsp` command to start server
- [ ] Test: LSP server responds to requests correctly

### 5.2 VSCode Extension

**Features:**
- Syntax highlighting
- Real-time diagnostics (via LSP)
- Hover info
- Auto-completion
- Go to definition
- "Play" button to play current file
- "Compile" button to compile to MIDI

**Tasks:**
- [ ] Create VSCode extension package (`vscode-pulang`)
- [ ] Add syntax highlighting (TextMate grammar `.tmLanguage.json`)
- [ ] Integrate LSP client (use `vscode-languageclient`)
- [ ] Add "Play" command in command palette
- [ ] Add "Compile" command
- [ ] Add play/compile buttons in editor toolbar
- [ ] Add file icon for `.pu` files
- [ ] Package extension (`.vsix` file)
- [ ] Publish to VSCode marketplace

### 5.3 Tree-sitter Grammar (Optional)

**Benefits:**
- Better syntax highlighting in GitHub, editors
- Incremental parsing for LSP (faster than re-parsing entire file)
- Standard grammar format used by many tools

**Tasks:**
- [ ] Port Lark grammar to Tree-sitter grammar
- [ ] Add to Tree-sitter grammar repository
- [ ] Use Tree-sitter parser in LSP for incremental parsing
- [ ] Test: Tree-sitter parser matches Lark parser output

### 5.4 Online Playground (Future)

**Features:**
- Monaco editor with .pu syntax highlighting
- Compile and play in browser
- Share snippets via URL

**Tasks:**
- [ ] Compile puLang to WebAssembly (or use Pyodide)
- [ ] Create web UI with Monaco editor
- [ ] Integrate Web Audio API for playback
- [ ] Add sharing functionality
- [ ] Deploy to static hosting

### Exit Criteria (Phase 5)

- [ ] VSCode extension provides great editing experience
- [ ] LSP provides real-time feedback on errors
- [ ] Users can develop .pu files comfortably in VSCode
- [ ] Syntax highlighting works in GitHub/GitLab

## Phase 6: Lifting (Analysis) Pipeline Support

**Goal:** Ensure the compiler tooling supports lifting Event/Score data into `.pu` files.

### 6.1 Decompilation commands
- [ ] Add `pulang decompile song.mid` command
- [ ] Implement `EventStream` -> `.pu` source code generation
- [ ] Test: Roundtrip parsing/decompilation

---

## Future Phases (Unscheduled)

These are ideas for future development, not committed roadmap items:

### Package Manager
```bash
pulang pkg install jazz-progressions
pulang pkg search "blues patterns"
```

- [ ] Design package format (bundled definitions, patterns)
- [ ] Implement package registry
- [ ] Add `pulang pkg` commands
- [ ] Support local and remote packages

### Debugger
```bash
pulang debug song.pu
(pudb) break section Verse
(pudb) continue
(pudb) print harmony
(pudb) step transform
```

- [ ] Interactive debugger for compilation
- [ ] Step through parsing, transformation, realization
- [ ] Visualize IR at each stage
- [ ] Inspect variables, tracks, patterns

### Performance Profiling
```bash
pulang profile song.pu
# Shows which transforms are slow, which patterns take time
```

- [ ] Add profiling instrumentation
- [ ] Report compilation time breakdown
- [ ] Report pattern realization performance
- [ ] Suggest optimizations

### Jupyter Kernel

- [ ] Implement Jupyter kernel for .pu
- [ ] Edit .pu in notebooks
- [ ] Inline playback in notebooks
- [ ] Visualize IR, MIDI output

### Testing Framework

```
# test_song.pu
test "verse harmony duration":
  section Verse [8 bars]:
    harmony: I IV V I

  expect harmony_duration = 8

test "bass in correct range":
  section Verse:
    Bass: pattern: root_quarters, octave: -2

  expect note_range(Bass) in (C2, C3)
```

- [ ] Add `test` blocks to .pu syntax
- [ ] Implement test runner: `pulang test song.pu`
- [ ] Support assertions on IR properties
- [ ] Support assertions on MIDI output

---

## Implementation Priorities

### Must Have (Phase 1)
- Basic compilation (.pu → MIDI)
- CLI commands (compile, play, check, show)
- Validation (errors/warnings)
- Documentation (tutorial, examples)

### Should Have (Phase 2)
- Feature parity with pypulang
- Watch mode (rapid iteration)
- Escape hatch (literal notes)
- Definitions/variables

### Nice to Have (Phase 3)
- Multi-file support
- Init command (onboarding)
- Format command (code quality)
- Great error messages

### Future (Phase 5+)
- LSP (IDE integration)
- VSCode extension (first-class editing)
- Tree-sitter grammar (ecosystem)
- Online playground (demos, tutorials)

---

## Dependencies Summary

### Core Dependencies (Phase 1)
```toml
[dependencies]
lark = ">=1.1.0"        # Parser
click = ">=8.0.0"       # CLI
```

### Phase 2
```toml
watchdog = ">=2.0.0"    # Watch mode
```

### Phase 3
```toml
rich = ">=10.0.0"       # Better terminal output (optional)
```

### Phase 4
```toml
pygls = ">=1.0.0"       # Language server
```

---

## Testing Strategy

### Test Categories

1. **Grammar tests** - Parse validity
   - Valid .pu files parse successfully
   - Invalid syntax raises clear errors
   - Edge cases (empty sections, comments, etc.)

2. **Semantic tests** - IR generation
   - Transformer produces correct IR structures
   - Symbol resolution works (variables, tracks)
   - Validation catches semantic errors

3. **Roundtrip tests** - Serialization
   - IR → JSON → IR preserves all data
   - Fractions, enums serialize correctly

4. **Structural tests** - MIDI output
   - Correct tempo, time signature, key
   - Correct number of tracks
   - Notes in expected ranges
   - Pattern realization produces correct rhythms

5. **CLI tests** - Command-line interface
   - All commands work with valid input
   - Error handling for invalid files
   - Help text is accurate

6. **Integration tests** - End-to-end
   - Compile example files, verify MIDI structure
   - Watch mode detects file changes
   - Multi-file imports work

### Test Coverage Target

- Minimum: 80% line coverage for Phase 1
- Goal: 90%+ line coverage for all phases

---

## Documentation Deliverables

### Phase 1
- `README.md` - Updated with puLang compiler section
- `docs/pulang-compiler-usage.md` - CLI usage guide
- `docs/pulang-tutorial.md` - Step-by-step tutorial
- `examples/pulang/*.pu` - 5+ example files with comments

### Phase 2
- Update docs with all new features
- Add advanced examples (multi-section, definitions, etc.)

### Phase 3
- `docs/pulang-multi-file.md` - Multi-file project guide
- `docs/pulang-style-guide.md` - Formatting conventions

### Phase 4
- `docs/pulang-lsp.md` - LSP setup and features
- VSCode extension README
- Online playground documentation

---

## Success Criteria

### Phase 1: Does it work?
- [ ] Can compile minimal .pu file to MIDI
- [ ] Can play .pu file with `pulang play`
- [ ] Validation catches common errors
- [ ] CLI is usable and documented

### Phase 2: Is it complete?
- [ ] Feature parity with pypulang
- [ ] Watch mode enables rapid iteration
- [ ] Can express complex compositions

### Phase 3: Is it polished?
- [ ] Error messages are excellent
- [ ] Multi-file projects work
- [ ] Formatter produces consistent style

### Phase 4: Is it production-ready?
- [ ] Great editing experience in VSCode
- [ ] LSP provides real-time feedback
- [ ] Used by real composers for real music

---

## Notes

- **Defer premature optimization:** Focus on correctness and usability first, performance later
- **Iterate on grammar:** Expect the .pu syntax to evolve based on real usage
- **Dogfood extensively:** Write real music with .pu to find rough edges
- **Maintain parity:** Keep pyPuLang and .pu semantics aligned
- **No REPL initially:** Use Python REPL with pypulang for interactive experimentation