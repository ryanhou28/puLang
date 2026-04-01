# puLang Style Guide

This document describes the code style conventions for the puLang project.

## Automated Formatting

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Ruff is fast and combines the functionality of multiple tools (flake8, isort, pyupgrade, etc.) into one.

### Quick Commands

```bash
# Check for linting issues
ruff check .

# Fix auto-fixable linting issues
ruff check --fix .

# Format code
ruff format .

# Check formatting without changing files
ruff format --check .
```

## Style

### Line Length

- Maximum 100 characters per line
- Ruff formatter handles wrapping automatically

### Imports

Imports are sorted automatically by Ruff into sections:

1. Standard library
2. Third-party packages
3. First-party (`pypulang`)

```python
# Good (auto-sorted)
from __future__ import annotations

from fractions import Fraction
from typing import List, Optional

import mido

from pypulang.ir.intent import Chord, Key
from pypulang.scales import get_scale_pitches
```

### Quotes

- Use double quotes `"` for strings (enforced by formatter)
- Docstrings use triple double quotes `"""`

### Type Hints

- Use type hints for function signatures
- Use `from __future__ import annotations` for modern syntax in Python 3.9+
- Prefer `list[int]` over `List[int]` when possible (Python 3.9+)

```python
from __future__ import annotations

def resolve_chord(chord: Chord, key: Key, octave: int = 4) -> list[int]:
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def resolve_chord(chord: Chord, key: Key, octave: int = 4) -> list[int]:
    """
    Resolve a roman numeral chord to MIDI pitches.

    Args:
        chord: A Chord object with roman numeral, quality, extensions, etc.
        key: The key context for resolution
        octave: Base octave for the chord (default 4)

    Returns:
        List of MIDI pitch numbers (sorted low to high)

    Examples:
        >>> resolve_chord(Chord("I", "major"), Key("C", "major"))
        [60, 64, 67]
    """
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Modules | `snake_case` | `resolution.py`, `scales.py` |
| Classes | `PascalCase` | `Chord`, `TimeSignature` |
| Functions | `snake_case` | `resolve_chord`, `get_bass_note` |
| Constants | `UPPER_SNAKE_CASE` | `PATTERN_REGISTRY`, `_MAJOR_SCALE` |
| Private | Leading underscore | `_build_chord_pitches` |

### Dataclasses

- Use `@dataclass` for IR types
- Use `frozen=True` for immutable types (most IR types)
- Include `to_dict()` and `from_dict()` methods for serialization

```python
@dataclass(frozen=True)
class Key:
    root: str
    mode: str = "major"

    def to_dict(self) -> dict[str, str]:
        return {"root": self.root, "mode": self.mode}

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> Key:
        return cls(root=d["root"], mode=d["mode"])
```

### Error Handling

- Raise `ValueError` for invalid inputs
- Include helpful error messages

```python
if key.mode not in _MODE_SCALES:
    raise ValueError(f"Unknown mode: {key.mode}")
```

### Testing

- Test files: `test_<module>.py`
- Test classes: `TestFeatureName`
- Test functions: `test_specific_behavior`
- Use pytest fixtures for shared setup
- Use hypothesis for property-based tests where appropriate

```python
class TestResolveChord:
    def test_c_major_I_returns_c_e_g(self):
        chord = Chord("I", "major")
        key = Key("C", "major")
        assert resolve_chord(chord, key, octave=4) == [60, 64, 67]
```

## Pre-commit Hook (Optional)

To automatically format on commit, create `.git/hooks/pre-commit`:

```bash
#!/bin/sh
ruff format .
ruff check --fix .
git add -u
```

Make it executable: `chmod +x .git/hooks/pre-commit`
