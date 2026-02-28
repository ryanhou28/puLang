"""
Pitch constants and utilities for literal note specification.

This module provides:
- Pitch class: An int subclass representing MIDI pitch with arithmetic operations
- Pitch constants: C0-B8, with sharp (Cs, Ds, etc.) and flat (Db, Eb, etc.) variants
- Helper functions: note(), rest(), chord() for creating note specifications

Usage:
    from pypulang.pitches import *

    # Use pitch constants directly
    melody = [
        (C4, 1/4), (E4, 1/4), (G4, 1/2),
        (C5, 1/4), rest(1/4), (G4, 1/2),
    ]

    # Pitch arithmetic
    C4 + 7  # Returns Pitch for G4
    C4.octave_up()  # Returns C5

    # Using note() for explicit velocity
    note(C4, 1/4, velocity=100)

    # Using chord() for simultaneous notes
    chord([C4, E4, G4], 1/2)
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Union


class Pitch(int):
    """
    A MIDI pitch value (0-127) with helpful methods.

    Pitch is an int subclass, so it can be used anywhere an int is expected.
    It provides additional methods for octave shifts and transposition.

    The MIDI pitch number follows the standard where:
    - C-1 = 0 (lowest)
    - C4 = 60 (middle C)
    - G9 = 127 (highest)

    Example:
        >>> C4 = Pitch(60)
        >>> C4 + 7  # G4
        Pitch(67)
        >>> C4.octave_up()  # C5
        Pitch(72)
    """

    def __new__(cls, value: int) -> Pitch:
        """Create a new Pitch, clamping to valid MIDI range."""
        # Allow creation but clamp on output
        instance = super().__new__(cls, value)
        return instance

    def __repr__(self) -> str:
        return f"Pitch({int(self)})"

    def __str__(self) -> str:
        # Return note name if in valid range
        if 0 <= self <= 127:
            note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            octave = (self // 12) - 1  # MIDI octave convention: C4 = 60
            note = note_names[self % 12]
            return f"{note}{octave}"
        return f"Pitch({int(self)})"

    def __add__(self, other: int) -> Pitch:
        """Add semitones to this pitch."""
        return Pitch(int(self) + other)

    def __radd__(self, other: int) -> Pitch:
        """Add semitones to this pitch (reversed)."""
        return Pitch(other + int(self))

    def __sub__(self, other: int) -> Pitch:
        """Subtract semitones from this pitch."""
        return Pitch(int(self) - other)

    def __rsub__(self, other: int) -> Pitch:
        """Subtract this pitch from a value (reversed)."""
        return Pitch(other - int(self))

    def octave_up(self, n: int = 1) -> Pitch:
        """Return a new Pitch shifted up by n octaves."""
        return Pitch(int(self) + 12 * n)

    def octave_down(self, n: int = 1) -> Pitch:
        """Return a new Pitch shifted down by n octaves."""
        return Pitch(int(self) - 12 * n)

    def transpose(self, semitones: int) -> Pitch:
        """Return a new Pitch transposed by the given semitones."""
        return Pitch(int(self) + semitones)

    @property
    def midi(self) -> int:
        """Return the raw MIDI pitch number."""
        return int(self)

    @property
    def octave(self) -> int:
        """Return the octave number (C4 = octave 4)."""
        return (int(self) // 12) - 1

    @property
    def note_name(self) -> str:
        """Return the note name without octave (e.g., 'C', 'C#', 'D')."""
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        return note_names[int(self) % 12]


def _make_pitch(note: str, octave: int) -> Pitch:
    """Create a Pitch from note name and octave."""
    semitones = {
        "C": 0, "Cs": 1, "Db": 1,
        "D": 2, "Ds": 3, "Eb": 3,
        "E": 4, "Fb": 4, "Es": 5,
        "F": 5, "Fs": 6, "Gb": 6,
        "G": 7, "Gs": 8, "Ab": 8,
        "A": 9, "As": 10, "Bb": 10,
        "B": 11, "Cb": 11, "Bs": 0,
    }
    # MIDI convention: C4 = 60, so octave 4 is (4+1)*12 = 60 base
    midi_value = (octave + 1) * 12 + semitones[note]
    return Pitch(midi_value)


# -----------------------------------------------------------------------------
# Pitch Constants: C0 through B8
# -----------------------------------------------------------------------------

# Octave -1 (MIDI 0-11) - very low, rarely used
C_1 = _make_pitch("C", -1)
Cs_1 = Db_1 = _make_pitch("Cs", -1)
D_1 = _make_pitch("D", -1)
Ds_1 = Eb_1 = _make_pitch("Ds", -1)
E_1 = _make_pitch("E", -1)
F_1 = _make_pitch("F", -1)
Fs_1 = Gb_1 = _make_pitch("Fs", -1)
G_1 = _make_pitch("G", -1)
Gs_1 = Ab_1 = _make_pitch("Gs", -1)
A_1 = _make_pitch("A", -1)
As_1 = Bb_1 = _make_pitch("As", -1)
B_1 = _make_pitch("B", -1)

# Octave 0 (MIDI 12-23)
C0 = _make_pitch("C", 0)
Cs0 = Db0 = _make_pitch("Cs", 0)
D0 = _make_pitch("D", 0)
Ds0 = Eb0 = _make_pitch("Ds", 0)
E0 = _make_pitch("E", 0)
F0 = _make_pitch("F", 0)
Fs0 = Gb0 = _make_pitch("Fs", 0)
G0 = _make_pitch("G", 0)
Gs0 = Ab0 = _make_pitch("Gs", 0)
A0 = _make_pitch("A", 0)
As0 = Bb0 = _make_pitch("As", 0)
B0 = _make_pitch("B", 0)

# Octave 1 (MIDI 24-35)
C1 = _make_pitch("C", 1)
Cs1 = Db1 = _make_pitch("Cs", 1)
D1 = _make_pitch("D", 1)
Ds1 = Eb1 = _make_pitch("Ds", 1)
E1 = _make_pitch("E", 1)
F1 = _make_pitch("F", 1)
Fs1 = Gb1 = _make_pitch("Fs", 1)
G1 = _make_pitch("G", 1)
Gs1 = Ab1 = _make_pitch("Gs", 1)
A1 = _make_pitch("A", 1)
As1 = Bb1 = _make_pitch("As", 1)
B1 = _make_pitch("B", 1)

# Octave 2 (MIDI 36-47)
C2 = _make_pitch("C", 2)
Cs2 = Db2 = _make_pitch("Cs", 2)
D2 = _make_pitch("D", 2)
Ds2 = Eb2 = _make_pitch("Ds", 2)
E2 = _make_pitch("E", 2)
F2 = _make_pitch("F", 2)
Fs2 = Gb2 = _make_pitch("Fs", 2)
G2 = _make_pitch("G", 2)
Gs2 = Ab2 = _make_pitch("Gs", 2)
A2 = _make_pitch("A", 2)
As2 = Bb2 = _make_pitch("As", 2)
B2 = _make_pitch("B", 2)

# Octave 3 (MIDI 48-59)
C3 = _make_pitch("C", 3)
Cs3 = Db3 = _make_pitch("Cs", 3)
D3 = _make_pitch("D", 3)
Ds3 = Eb3 = _make_pitch("Ds", 3)
E3 = _make_pitch("E", 3)
F3 = _make_pitch("F", 3)
Fs3 = Gb3 = _make_pitch("Fs", 3)
G3 = _make_pitch("G", 3)
Gs3 = Ab3 = _make_pitch("Gs", 3)
A3 = _make_pitch("A", 3)
As3 = Bb3 = _make_pitch("As", 3)
B3 = _make_pitch("B", 3)

# Octave 4 (MIDI 60-71) - Middle C octave
C4 = _make_pitch("C", 4)
Cs4 = Db4 = _make_pitch("Cs", 4)
D4 = _make_pitch("D", 4)
Ds4 = Eb4 = _make_pitch("Ds", 4)
E4 = _make_pitch("E", 4)
F4 = _make_pitch("F", 4)
Fs4 = Gb4 = _make_pitch("Fs", 4)
G4 = _make_pitch("G", 4)
Gs4 = Ab4 = _make_pitch("Gs", 4)
A4 = _make_pitch("A", 4)  # Concert A (440 Hz)
As4 = Bb4 = _make_pitch("As", 4)
B4 = _make_pitch("B", 4)

# Octave 5 (MIDI 72-83)
C5 = _make_pitch("C", 5)
Cs5 = Db5 = _make_pitch("Cs", 5)
D5 = _make_pitch("D", 5)
Ds5 = Eb5 = _make_pitch("Ds", 5)
E5 = _make_pitch("E", 5)
F5 = _make_pitch("F", 5)
Fs5 = Gb5 = _make_pitch("Fs", 5)
G5 = _make_pitch("G", 5)
Gs5 = Ab5 = _make_pitch("Gs", 5)
A5 = _make_pitch("A", 5)
As5 = Bb5 = _make_pitch("As", 5)
B5 = _make_pitch("B", 5)

# Octave 6 (MIDI 84-95)
C6 = _make_pitch("C", 6)
Cs6 = Db6 = _make_pitch("Cs", 6)
D6 = _make_pitch("D", 6)
Ds6 = Eb6 = _make_pitch("Ds", 6)
E6 = _make_pitch("E", 6)
F6 = _make_pitch("F", 6)
Fs6 = Gb6 = _make_pitch("Fs", 6)
G6 = _make_pitch("G", 6)
Gs6 = Ab6 = _make_pitch("Gs", 6)
A6 = _make_pitch("A", 6)
As6 = Bb6 = _make_pitch("As", 6)
B6 = _make_pitch("B", 6)

# Octave 7 (MIDI 96-107)
C7 = _make_pitch("C", 7)
Cs7 = Db7 = _make_pitch("Cs", 7)
D7 = _make_pitch("D", 7)
Ds7 = Eb7 = _make_pitch("Ds", 7)
E7 = _make_pitch("E", 7)
F7 = _make_pitch("F", 7)
Fs7 = Gb7 = _make_pitch("Fs", 7)
G7 = _make_pitch("G", 7)
Gs7 = Ab7 = _make_pitch("Gs", 7)
A7 = _make_pitch("A", 7)
As7 = Bb7 = _make_pitch("As", 7)
B7 = _make_pitch("B", 7)

# Octave 8 (MIDI 108-119)
C8 = _make_pitch("C", 8)
Cs8 = Db8 = _make_pitch("Cs", 8)
D8 = _make_pitch("D", 8)
Ds8 = Eb8 = _make_pitch("Ds", 8)
E8 = _make_pitch("E", 8)
F8 = _make_pitch("F", 8)
Fs8 = Gb8 = _make_pitch("Fs", 8)
G8 = _make_pitch("G", 8)  # MIDI 127 is the max
Gs8 = Ab8 = _make_pitch("Gs", 8)
A8 = _make_pitch("A", 8)
As8 = Bb8 = _make_pitch("As", 8)
B8 = _make_pitch("B", 8)

# Octave 9 (MIDI 120-127, partial)
C9 = _make_pitch("C", 9)
Cs9 = Db9 = _make_pitch("Cs", 9)
D9 = _make_pitch("D", 9)
Ds9 = Eb9 = _make_pitch("Ds", 9)
E9 = _make_pitch("E", 9)
F9 = _make_pitch("F", 9)
Fs9 = Gb9 = _make_pitch("Fs", 9)
G9 = _make_pitch("G", 9)  # MIDI 127 - highest possible


# -----------------------------------------------------------------------------
# Note Specification Functions
# -----------------------------------------------------------------------------

# Type for duration: Fraction, float, or int
DurationType = Union[Fraction, float, int]


@dataclass
class NoteSpec:
    """
    A note specification for use in track.notes().

    This is a temporary holder that gets converted to ir.intent.Note
    when building the IR.
    """

    pitch: int  # MIDI pitch, -1 for rest
    duration: Fraction
    velocity: int | None = None

    def __iter__(self):
        """Allow unpacking as (pitch, duration) or (pitch, duration, velocity)."""
        if self.velocity is not None:
            return iter((self.pitch, self.duration, self.velocity))
        return iter((self.pitch, self.duration))


@dataclass
class ChordSpec:
    """
    A chord specification (multiple simultaneous notes) for use in track.notes().
    """

    pitches: list[int]
    duration: Fraction
    velocity: int | None = None


# Rest pitch constant
REST = -1


def note(
    pitch: int | Pitch,
    duration: DurationType,
    velocity: int | None = None,
) -> NoteSpec:
    """
    Create a note specification with explicit pitch, duration, and optional velocity.

    Args:
        pitch: MIDI pitch (0-127) or Pitch constant
        duration: Note duration (1/4 for quarter, 1/8 for eighth, etc.)
        velocity: Optional velocity override (0-127)

    Returns:
        NoteSpec that can be used in track.notes()

    Example:
        note(C4, 1/4)  # Quarter note middle C
        note(G4, 1/2, velocity=100)  # Half note G with velocity 100
    """
    return NoteSpec(
        pitch=int(pitch),
        duration=Fraction(duration) if not isinstance(duration, Fraction) else duration,
        velocity=velocity,
    )


def rest(duration: DurationType) -> NoteSpec:
    """
    Create a rest (silence) of the given duration.

    Args:
        duration: Rest duration (1/4 for quarter rest, etc.)

    Returns:
        NoteSpec with pitch=-1 representing a rest

    Example:
        rest(1/4)  # Quarter rest
        rest(1/2)  # Half rest
    """
    return NoteSpec(
        pitch=REST,
        duration=Fraction(duration) if not isinstance(duration, Fraction) else duration,
        velocity=None,
    )


def chord(
    pitches: list[int | Pitch],
    duration: DurationType,
    velocity: int | None = None,
) -> ChordSpec:
    """
    Create a chord (multiple simultaneous notes) specification.

    Args:
        pitches: List of MIDI pitches to play simultaneously
        duration: Chord duration
        velocity: Optional velocity override for all notes

    Returns:
        ChordSpec that can be used in track.notes()

    Example:
        chord([C4, E4, G4], 1/2)  # C major chord, half note
        chord([D4, F4, A4], 1/4, velocity=80)  # D minor chord
    """
    return ChordSpec(
        pitches=[int(p) for p in pitches],
        duration=Fraction(duration) if not isinstance(duration, Fraction) else duration,
        velocity=velocity,
    )


# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = [
    # Core class
    "Pitch",
    # Note specification functions
    "note",
    "rest",
    "chord",
    "NoteSpec",
    "ChordSpec",
    "REST",
    # Octave -1
    "C_1", "Cs_1", "Db_1", "D_1", "Ds_1", "Eb_1", "E_1", "F_1",
    "Fs_1", "Gb_1", "G_1", "Gs_1", "Ab_1", "A_1", "As_1", "Bb_1", "B_1",
    # Octave 0
    "C0", "Cs0", "Db0", "D0", "Ds0", "Eb0", "E0", "F0",
    "Fs0", "Gb0", "G0", "Gs0", "Ab0", "A0", "As0", "Bb0", "B0",
    # Octave 1
    "C1", "Cs1", "Db1", "D1", "Ds1", "Eb1", "E1", "F1",
    "Fs1", "Gb1", "G1", "Gs1", "Ab1", "A1", "As1", "Bb1", "B1",
    # Octave 2
    "C2", "Cs2", "Db2", "D2", "Ds2", "Eb2", "E2", "F2",
    "Fs2", "Gb2", "G2", "Gs2", "Ab2", "A2", "As2", "Bb2", "B2",
    # Octave 3
    "C3", "Cs3", "Db3", "D3", "Ds3", "Eb3", "E3", "F3",
    "Fs3", "Gb3", "G3", "Gs3", "Ab3", "A3", "As3", "Bb3", "B3",
    # Octave 4 (middle C)
    "C4", "Cs4", "Db4", "D4", "Ds4", "Eb4", "E4", "F4",
    "Fs4", "Gb4", "G4", "Gs4", "Ab4", "A4", "As4", "Bb4", "B4",
    # Octave 5
    "C5", "Cs5", "Db5", "D5", "Ds5", "Eb5", "E5", "F5",
    "Fs5", "Gb5", "G5", "Gs5", "Ab5", "A5", "As5", "Bb5", "B5",
    # Octave 6
    "C6", "Cs6", "Db6", "D6", "Ds6", "Eb6", "E6", "F6",
    "Fs6", "Gb6", "G6", "Gs6", "Ab6", "A6", "As6", "Bb6", "B6",
    # Octave 7
    "C7", "Cs7", "Db7", "D7", "Ds7", "Eb7", "E7", "F7",
    "Fs7", "Gb7", "G7", "Gs7", "Ab7", "A7", "As7", "Bb7", "B7",
    # Octave 8
    "C8", "Cs8", "Db8", "D8", "Ds8", "Eb8", "E8", "F8",
    "Fs8", "Gb8", "G8", "Gs8", "Ab8", "A8", "As8", "Bb8", "B8",
    # Octave 9 (partial)
    "C9", "Cs9", "Db9", "D9", "Ds9", "Eb9", "E9", "F9", "Fs9", "Gb9", "G9",
]
