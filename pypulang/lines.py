"""
Melody notation.

    "a4/8 c5 e5/4. r/8 | g5/2~ g5/8 f5 e5/4"

A token is a pitch and an optional note value, which carries over until the next
one is given. Values are 1, 2, 4, 8, 16, 32, with "." for dotted and "t" for a
triplet. "r" is a rest. Suffixes change the note: ">" accents it, "?" makes it a
ghost, "'" plays it staccato, and "~" ties it into the next note. "|" checks that the
bar adds up, which catches most mistakes in a long line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

_LETTERS = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
_TOKEN_RE = re.compile(
    r"^(?:(?P<rest>r)|(?P<letter>[a-g])(?P<acc>#|b)?(?P<octave>-?\d))"
    r"(?:/(?P<value>\d+)(?P<dot>\.)?(?P<triplet>t)?)?"
    r"(?P<suffix>[>?'~]*)$"
)


@dataclass(frozen=True)
class LineNote:
    """A note in beats. `pitch` is -1 for a rest."""

    pitch: int
    start: Fraction
    dur: Fraction
    velocity_scale: Fraction
    articulation: str | None


def _value(number: str, dotted: bool, triplet: bool) -> Fraction:
    beats = Fraction(4, int(number))
    if dotted:
        beats *= Fraction(3, 2)
    if triplet:
        beats *= Fraction(2, 3)
    return beats


def parse_line(text: str, bar_beats: Fraction | None = None) -> list[LineNote]:
    """
    Read a melody.

    Args:
        text: The line
        bar_beats: Length of a bar in beats, to check "|" against. None skips the check.

    Raises:
        ValueError: On a token that cannot be read, or a bar that does not add up
    """
    notes: list[LineNote] = []
    at = Fraction(0)
    bar_start = Fraction(0)
    value = Fraction(1)
    tied = False
    for token in text.replace("|", " | ").split():
        if token == "|":
            if bar_beats is not None and at - bar_start != bar_beats:
                raise ValueError(
                    f"Bar ending at beat {at} holds {at - bar_start} beats, not {bar_beats}: "
                    f"{text!r}"
                )
            bar_start = at
            continue
        m = _TOKEN_RE.match(token)
        if m is None:
            raise ValueError(f"Cannot read {token!r} in {text!r}")
        if m.group("value"):
            value = _value(m.group("value"), bool(m.group("dot")), bool(m.group("triplet")))
        if m.group("rest"):
            at += value
            tied = False
            continue
        offset = {"#": 1, "b": -1, None: 0}[m.group("acc")]
        pitch = (int(m.group("octave")) + 1) * 12 + _LETTERS[m.group("letter")] + offset
        suffix = m.group("suffix")
        if tied and notes and notes[-1].pitch == pitch:
            last = notes[-1]
            notes[-1] = LineNote(
                last.pitch, last.start, last.dur + value, last.velocity_scale, last.articulation
            )
        else:
            scale = Fraction(6, 5) if ">" in suffix else Fraction(1)
            if "?" in suffix:
                scale = Fraction(1, 2)
            notes.append(LineNote(pitch, at, value, scale, "staccato" if "'" in suffix else None))
        tied = "~" in suffix
        at += value
    return notes
