"""
Chord resolution for puLang.

This module resolves abstract chord representations (roman numerals) into
concrete MIDI pitches. It's a key part of the Intent IR → Event IR pipeline.
"""

from __future__ import annotations

from pypulang.harmony import chord_intervals
from pypulang.ir.intent import Chord, Key
from pypulang.scales import get_scale_pitches, pitch_class_to_semitone


def resolve_chord(chord: Chord, key: Key, octave: int = 4) -> list[int]:
    """
    Resolve a roman numeral chord to MIDI pitches.

    This is the core function that converts Intent IR chord representations
    into concrete pitches that can be played.

    Args:
        chord: A Chord object with roman numeral, quality, extensions, etc.
        key: The key context for resolution
        octave: Base octave for the chord (default 4)

    Returns:
        List of MIDI pitch numbers (sorted low to high)

    Examples:
        >>> resolve_chord(Chord("I", "major"), Key("C", "major"))
        [60, 64, 67]  # C4, E4, G4

        >>> resolve_chord(Chord("V", "major", extensions=("7",)), Key("C", "major"))
        [67, 71, 74, 77]  # G4, B4, D5, F5

        >>> resolve_chord(Chord("vi", "minor"), Key("C", "major"))
        [69, 72, 76]  # A4, C5, E5
    """
    # Get scale intervals for this key
    scale = get_scale_pitches(key)

    # Get root pitch of the key
    key_root = pitch_class_to_semitone(key.root)

    # Determine the chord root
    degree = chord.degree  # 1-7
    scale_index = degree - 1  # 0-6

    # Apply altered root (for bVII, #IV, etc.)
    chord_root_offset = scale[scale_index] + chord.altered_root

    # Handle secondary dominants (V/V, V/vi, etc.)
    if chord.secondary:
        # Find the target chord's root
        secondary_degree = _numeral_to_degree(chord.secondary)
        secondary_root_offset = scale[secondary_degree - 1]
        # The chord is built on the 5th of the secondary target
        # V/V means "the V chord of the V chord" = build major chord on scale degree 2
        # For a true secondary dominant, we need to calculate a fifth above the target
        chord_root_offset = (secondary_root_offset + 7) % 12  # Fifth above target

    # Calculate actual MIDI pitch for chord root
    base_pitch = 12 + (octave * 12) + ((key_root + chord_root_offset) % 12)

    # Build the chord based on quality
    pitches = _build_chord_pitches(base_pitch, chord.quality, chord.extensions)

    # Apply inversion
    pitches = _apply_inversion(pitches, chord.inversion)

    # A slash bass goes under everything, in the octave just below the chord.
    if chord.bass_offset is not None:
        bass_pc = (key_root + chord.bass_offset) % 12
        bass = pitches[0] - ((pitches[0] - bass_pc) % 12 or 12)
        pitches = [bass] + pitches

    return pitches


def _numeral_to_degree(numeral: str) -> int:
    """Convert a numeral string to a scale degree (1-7)."""
    numeral_map = {
        "I": 1,
        "II": 2,
        "III": 3,
        "IV": 4,
        "V": 5,
        "VI": 6,
        "VII": 7,
        "i": 1,
        "ii": 2,
        "iii": 3,
        "iv": 4,
        "v": 5,
        "vi": 6,
        "vii": 7,
    }
    if numeral not in numeral_map:
        raise ValueError(f"Invalid numeral: {numeral}")
    return numeral_map[numeral]


def _build_chord_pitches(root: int, quality: str, extensions: tuple[str, ...]) -> list[int]:
    """
    Build chord pitches from root, quality, and extensions.

    Args:
        root: MIDI pitch of chord root
        quality: "major", "minor", "diminished", "augmented"
        extensions: Tuple of extension strings like "7", "maj7", "9", etc.

    Returns:
        List of MIDI pitches, sorted low to high

    Raises:
        ValueError: If an extension is not a known chord token
    """
    return [root + tone.interval for tone in chord_intervals(quality, extensions)]


def _apply_inversion(pitches: list[int], inversion: int) -> list[int]:
    """
    Apply chord inversion by raising bass notes by an octave.

    Args:
        pitches: List of MIDI pitches (sorted low to high)
        inversion: 0=root, 1=first, 2=second, 3=third

    Returns:
        Inverted chord pitches (sorted)
    """
    if inversion == 0:
        return pitches

    pitches = list(pitches)  # Copy to avoid mutation

    for _ in range(inversion):
        if len(pitches) > 1:
            # Move lowest note up an octave
            lowest = pitches.pop(0)
            pitches.append(lowest + 12)

    return sorted(pitches)


def get_chord_root_pitch(chord: Chord, key: Key, octave: int = 4) -> int:
    """
    Get just the root pitch of a chord (useful for bass lines).

    Args:
        chord: A Chord object
        key: The key context
        octave: Base octave

    Returns:
        MIDI pitch of chord root
    """
    scale = get_scale_pitches(key)
    key_root = pitch_class_to_semitone(key.root)

    degree = chord.degree
    scale_index = degree - 1
    chord_root_offset = scale[scale_index] + chord.altered_root

    if chord.secondary:
        secondary_degree = _numeral_to_degree(chord.secondary)
        secondary_root_offset = scale[secondary_degree - 1]
        chord_root_offset = (secondary_root_offset + 7) % 12

    return 12 + (octave * 12) + ((key_root + chord_root_offset) % 12)


def get_bass_note(chord: Chord, key: Key, octave: int = 2) -> int:
    """
    Get the bass note for a chord, respecting inversions.

    For inverted chords, the bass is not the root:
    - First inversion: 3rd in bass
    - Second inversion: 5th in bass

    Args:
        chord: A Chord object
        key: The key context
        octave: Bass octave (default 2)

    Returns:
        MIDI pitch of the bass note
    """
    # Get all chord tones at the given octave
    pitches = resolve_chord(chord, key, octave)

    # The lowest note after inversion is the bass
    return min(pitches)
