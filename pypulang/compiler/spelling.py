"""Pitch names for the `score` dialect."""

from __future__ import annotations

import re

from pypulang.harmony import prefers_flats
from pypulang.ir.intent import Key

_SHARPS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_FLATS = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
_NATURALS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NAME_RE = re.compile(r"^([A-G])(#|b)?(-?\d+)$")


def spell(midi: int, key: Key) -> str:
    """The name of a MIDI pitch in a key, where 60 is C4."""
    names = _FLATS if prefers_flats(key) else _SHARPS
    return f"{names[midi % 12]}{midi // 12 - 1}"


def midi_of(name: str) -> int:
    """The MIDI pitch of a name written by `spell`."""
    m = _NAME_RE.match(name)
    if m is None:
        raise ValueError(f"Not a pitch name: {name!r}")
    accidental = {None: 0, "#": 1, "b": -1}[m.group(2)]
    return (int(m.group(3)) + 1) * 12 + _NATURALS[m.group(1)] + accidental
