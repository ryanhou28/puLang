"""
Reharmonization: rewriting a progression while keeping its shape.

These are pure functions on chords, used both by `SectionBuilder.transform` and by
the `reharmonize` pass. They are statements about harmony, so they belong at this
level, far above anything a DAW is asked to understand.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction

from pypulang.harmony import _NUMERALS, _degree_of, chord_shape, root_pitch_class
from pypulang.ir.intent import Chord, ChordChange, Harmony, Key
from pypulang.scales import get_scale_pitches, pitch_class_to_semitone

_SEVENTH_TOKENS = frozenset({"7", "9", "11", "13", "alt"})


def is_dominant(chord: Chord) -> bool:
    """True for a major-third chord with a flat seventh."""
    return chord.quality == "major" and bool(_SEVENTH_TOKENS & set(chord.extensions))


def _on_root(chord: Chord, root_pc: int, key: Key) -> Chord:
    """The same chord built on another root."""
    offset = (root_pc - pitch_class_to_semitone(key.root)) % 12
    degree, altered = _degree_of(offset, key)
    numeral = _NUMERALS[degree - 1]
    if chord.quality in ("minor", "diminished"):
        numeral = numeral.lower()
    return replace(chord, numeral=numeral, altered_root=altered, secondary=None)


def tritone_sub(chord: Chord, key: Key) -> Chord:
    """A dominant replaced by the dominant a tritone away, which shares its guide tones."""
    if not is_dominant(chord):
        return chord
    return _on_root(chord, (root_pitch_class(chord, key) + 6) % 12, key)


def _diatonic_seventh(chord: Chord, key: Key) -> tuple[str, ...]:
    """The seventh that belongs on this chord in this key."""
    root = pitch_class_to_semitone(key.root)
    scale = [(root + s) % 12 for s in get_scale_pitches(key)]
    chord_root = root_pitch_class(chord, key)
    if chord_root not in scale:
        return ("7",)
    major_seventh = (chord_root + 11) % 12 in scale
    return ("maj7",) if major_seventh else ("7",)


def jazzify(chord: Chord, key: Key) -> Chord:
    """Triads become seventh chords, and sevenths gain a ninth."""
    shape = chord_shape(chord, key)
    names = {t.function for t in shape.tones}
    if chord.quality == "diminished" or "b9" in names or "#9" in names:
        return chord
    if "7" not in names and "6" not in names:
        return replace(chord, extensions=(*chord.extensions, *_diatonic_seventh(chord, key)))
    if "9" not in names:
        return replace(chord, extensions=(*chord.extensions, "9"))
    return chord


def modal_interchange(chord: Chord, key: Key) -> Chord:
    """Borrow from the parallel minor: IV becomes iv, and vi becomes bVI."""
    if key.mode != "major" or chord.altered_root or chord.secondary:
        return chord
    if chord.numeral == "IV":
        return replace(chord, numeral="iv", quality="minor")
    if chord.numeral == "vi":
        return replace(chord, numeral="VI", quality="major", altered_root=-1)
    if chord.numeral == "iii":
        return replace(chord, numeral="III", quality="major", altered_root=-1)
    if chord.numeral == "ii":
        return replace(chord, quality="diminished", extensions=("7",))
    return chord


ChordRewrite = Callable[[Chord, Key], Chord]
CHORD_REWRITES: dict[str, ChordRewrite] = {
    "tritone_sub": tritone_sub,
    "jazzify": jazzify,
    "modal_interchange": modal_interchange,
}


def secondary_dominants(changes: list[ChordChange], key: Key) -> list[ChordChange]:
    """
    Precede each chord with its own V7, taking the back half of the chord before.

    Tonic and already-dominant targets are left alone, as is anything too short to
    give up half its length.
    """
    result: list[ChordChange] = []
    for index, change in enumerate(changes):
        following = changes[(index + 1) % len(changes)].chord
        target_root = root_pitch_class(following, key)
        skip = (
            index + 1 == len(changes)
            or is_dominant(change.chord)
            or target_root == pitch_class_to_semitone(key.root)
            or is_dominant(following)
            or change.duration <= Fraction(1, 2)
        )
        if skip:
            result.append(change)
            continue
        half = change.duration / 2
        dominant = _on_root(Chord("V", extensions=("7",)), (target_root + 7) % 12, key)
        result.append(ChordChange(chord=change.chord, duration=half))
        result.append(ChordChange(chord=dominant, duration=half))
    return result


def reharmonize(changes: list[ChordChange], key: Key, strategy: str) -> list[ChordChange]:
    """
    Apply a named reharmonization.

    Args:
        changes: The progression
        key: Its key
        strategy: One of `STRATEGIES`

    Raises:
        KeyError: If the strategy does not exist
    """
    if strategy in ("secondary_dominants", "secondary_dominant"):
        return secondary_dominants(changes, key)
    if strategy not in CHORD_REWRITES:
        raise KeyError(f"Unknown reharmonization: {strategy}. Available: {STRATEGIES}")
    rewrite = CHORD_REWRITES[strategy]
    return [ChordChange(chord=rewrite(c.chord, key), duration=c.duration) for c in changes]


STRATEGIES = (*CHORD_REWRITES, "secondary_dominants")


_FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
_SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def transposed_key(key: Key, semitones: int) -> Key:
    """The same mode on another tonic, spelled the way that key is usually written."""
    pc = (pitch_class_to_semitone(key.root) + semitones) % 12
    names = _FLAT_NAMES if pc in (1, 3, 5, 8, 10) else _SHARP_NAMES
    return Key(names[pc], key.mode)


def harmony_with(harmony: Harmony, changes: list[ChordChange]) -> Harmony:
    return Harmony(changes=changes, duration_unit=harmony.duration_unit)
