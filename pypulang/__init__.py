"""
pypulang - Python-embedded DSL for puLang music composition.

Phase 1: Minimal Playable Prototype

Usage:
    from pypulang import *

    with piece(tempo=100, key="C major") as p:
        verse = p.section("verse", bars=4)
        verse.harmony(I, IV, vi, V)
        verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

    p.save_midi("output.mid")
"""

__version__ = "0.1.0"

# Core IR types (for advanced usage)
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

# MIDI emission
from pypulang.midi import (
    realize_to_midi,
    save_midi,
)

# Pattern generators (for advanced usage)
from pypulang.patterns import (
    PATTERN_REGISTRY,
    generate_pattern,
    get_pattern,
    register_pattern,
)

# Chord resolution (for advanced usage)
from pypulang.resolution import (
    get_bass_note,
    get_chord_root_pitch,
    resolve_chord,
)

# Scale utilities (for advanced usage)
from pypulang.scales import (
    get_key_root_pitch,
    get_scale_pitches,
    pitch_class_to_semitone,
)

# DSL - Main user-facing API
from pypulang.dsl import (
    # Main entry point
    piece,
    # Role enum
    Role,
    # Roman numeral constants - Major
    I,
    II,
    III,
    IV,
    V,
    VI,
    VII,
    # Roman numeral constants - Minor
    i,
    ii,
    iii,
    iv,
    v,
    vi,
    vii,
    # Common 7th chords
    I7,
    II7,
    III7,
    IV7,
    V7,
    VI7,
    VII7,
    Imaj7,
    IVmaj7,
    ii7,
    iii7,
    vi7,
    vii7,
    # Pattern singletons
    root_quarters,
    root_eighths,
    root_fifths,
    block_chords,
    arp,
    # Builder classes (for type hints)
    PieceBuilder,
    SectionBuilder,
    TrackBuilder,
    PatternBuilder,
    RomanNumeral,
)

__all__ = [
    # Version
    "__version__",
    # DSL - Main API
    "piece",
    "Role",
    # Roman numerals - Major
    "I",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    # Roman numerals - Minor
    "i",
    "ii",
    "iii",
    "iv",
    "v",
    "vi",
    "vii",
    # Common 7th chords
    "I7",
    "II7",
    "III7",
    "IV7",
    "V7",
    "VI7",
    "VII7",
    "Imaj7",
    "IVmaj7",
    "ii7",
    "iii7",
    "vi7",
    "vii7",
    # Pattern singletons
    "root_quarters",
    "root_eighths",
    "root_fifths",
    "block_chords",
    "arp",
    # Builder classes
    "PieceBuilder",
    "SectionBuilder",
    "TrackBuilder",
    "PatternBuilder",
    "RomanNumeral",
    # IR types (advanced)
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
    # Theory functions (advanced)
    "resolve_chord",
    "get_chord_root_pitch",
    "get_bass_note",
    "pitch_class_to_semitone",
    "get_scale_pitches",
    "get_key_root_pitch",
    # Pattern functions (advanced)
    "PATTERN_REGISTRY",
    "generate_pattern",
    "get_pattern",
    "register_pattern",
    # MIDI emission
    "realize_to_midi",
    "save_midi",
]
