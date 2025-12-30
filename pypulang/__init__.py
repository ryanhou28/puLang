"""
pypulang - Python-embedded DSL for puLang music composition.

Phase 1: Minimal Playable Prototype
"""

__version__ = "0.1.0"

# Core IR types
from pypulang.ir.intent import (
    Chord,
    ChordChange,
    Harmony,
    Key,
    Note,
    Notes,
    Pattern,
    Piece,
    Section,
    TimeSignature,
    Track,
)

# Pattern generators
from pypulang.patterns import (
    PATTERN_REGISTRY,
    generate_pattern,
    get_pattern,
    register_pattern,
)

# Chord resolution
from pypulang.resolution import (
    get_bass_note,
    get_chord_root_pitch,
    resolve_chord,
)

# Scale utilities
from pypulang.scales import (
    get_key_root_pitch,
    get_scale_pitches,
    pitch_class_to_semitone,
)

__all__ = [
    # Version
    "__version__",
    # IR types
    "Key",
    "TimeSignature",
    "Chord",
    "ChordChange",
    "Harmony",
    "Pattern",
    "Note",
    "Notes",
    "Track",
    "Section",
    "Piece",
    # Theory functions
    "resolve_chord",
    "get_chord_root_pitch",
    "get_bass_note",
    "pitch_class_to_semitone",
    "get_scale_pitches",
    "get_key_root_pitch",
    # Pattern functions
    "PATTERN_REGISTRY",
    "generate_pattern",
    "get_pattern",
    "register_pattern",
]
