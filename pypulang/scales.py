"""
Scale and pitch utilities for puLang.

This module provides low-level functions for working with pitches, scales,
and keys. These are the building blocks used by higher-level modules like
resolution.py.
"""

from __future__ import annotations

from pypulang.ir.intent import Key

# MIDI note numbers for C0 through B0 (octave 0)
# C0 = 12, C#0/Db0 = 13, ... B0 = 23
# Middle C (C4) = 60
_NOTE_TO_SEMITONE = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}

# Accidental adjustments
_ACCIDENTAL_OFFSET = {
    "": 0,
    "#": 1,
    "b": -1,
}


def pitch_class_to_semitone(pitch_class: str) -> int:
    """
    Convert a pitch class name (C, C#, Db, etc.) to semitones from C.

    Args:
        pitch_class: A note name like "C", "F#", "Bb"

    Returns:
        Semitones from C (0-11)

    Examples:
        >>> pitch_class_to_semitone("C")
        0
        >>> pitch_class_to_semitone("G")
        7
        >>> pitch_class_to_semitone("F#")
        6
    """
    if len(pitch_class) == 1:
        note = pitch_class
        accidental = ""
    else:
        note = pitch_class[0]
        accidental = pitch_class[1:]

    if note not in _NOTE_TO_SEMITONE:
        raise ValueError(f"Invalid note: {note}")

    if accidental not in _ACCIDENTAL_OFFSET:
        raise ValueError(f"Invalid accidental: {accidental}")

    return (_NOTE_TO_SEMITONE[note] + _ACCIDENTAL_OFFSET[accidental]) % 12


# Scale intervals from root in semitones
# Major scale: W W H W W W H
_MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]

# Natural minor scale: W H W W H W W
_MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]

# Mode intervals (all relative to major scale starting points)
_MODE_SCALES = {
    "major": _MAJOR_SCALE,
    "minor": _MINOR_SCALE,  # Natural minor = Aeolian
    "aeolian": _MINOR_SCALE,
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
}


def get_scale_pitches(key: Key) -> list[int]:
    """
    Get the scale degrees as semitones from the key root.

    Args:
        key: A Key object

    Returns:
        List of 7 semitone offsets from root (0-11)

    Examples:
        >>> get_scale_pitches(Key("C", "major"))
        [0, 2, 4, 5, 7, 9, 11]
        >>> get_scale_pitches(Key("A", "minor"))
        [0, 2, 3, 5, 7, 8, 10]
    """
    if key.mode not in _MODE_SCALES:
        raise ValueError(f"Unknown mode: {key.mode}")
    return _MODE_SCALES[key.mode]


def get_key_root_pitch(key: Key, octave: int = 4) -> int:
    """
    Get the MIDI pitch for the root of a key at a given octave.

    Args:
        key: A Key object
        octave: Octave number (default 4, where C4 = 60)

    Returns:
        MIDI pitch number

    Examples:
        >>> get_key_root_pitch(Key("C", "major"), octave=4)
        60
        >>> get_key_root_pitch(Key("A", "major"), octave=4)
        69
    """
    semitone = pitch_class_to_semitone(key.root)
    return 12 + (octave * 12) + semitone
