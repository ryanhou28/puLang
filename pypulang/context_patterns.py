"""
Patterns that can see their surroundings.

The original patterns in `patterns.py` receive a list of pitches. These receive a
`PatternContext`: the chord and the next one, the key, the meter, and where in the
section they are. A walking bass line cannot be written without that.

Randomness is seeded from the slot's source location, so a compile is repeatable
and changing one chord cannot reshuffle the rest of the piece.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from pypulang.harmony import ChordShape, chord_shape
from pypulang.ir.intent import Chord, Key, TimeSignature
from pypulang.rhythm import read_cell, scaled_velocity
from pypulang.scales import get_scale_pitches, pitch_class_to_semitone


@dataclass
class Event:
    """A note a pattern produced, in absolute beats."""

    pitch: int
    start: Fraction
    dur: Fraction
    vel: int
    articulation: str | None = None


@dataclass
class PatternContext:
    """Everything a pattern may ask about the moment it is filling."""

    pitches: list[int]
    next_pitches: list[int] | None
    chord: Chord
    next_chord: Chord | None
    key: Key
    meter: TimeSignature
    start: Fraction
    dur: Fraction
    section_offset: Fraction
    params: dict[str, Any]
    octave: int
    velocity: int
    seed: str
    _shape: ChordShape | None = field(default=None, repr=False)

    @property
    def shape(self) -> ChordShape:
        if self._shape is None:
            self._shape = chord_shape(self.chord, self.key)
        return self._shape

    @property
    def next_shape(self) -> ChordShape | None:
        return None if self.next_chord is None else chord_shape(self.next_chord, self.key)

    @property
    def bar_beats(self) -> Fraction:
        return self.meter.beats_per_bar

    def rng(self, salt: str = "") -> random.Random:
        digest = hashlib.sha256(f"{self.seed}|{salt}|{self.params.get('seed', '')}".encode())
        return random.Random(int.from_bytes(digest.digest()[:8], "big"))

    def scale_pcs(self) -> list[int]:
        """The pitch classes of the key's scale, starting from its tonic."""
        root = pitch_class_to_semitone(self.key.root)
        return [(root + s) % 12 for s in get_scale_pitches(self.key)]


ContextPattern = Callable[[PatternContext], list[Event]]
CONTEXT_PATTERNS: dict[str, ContextPattern] = {}


def context_pattern(name: str) -> Callable[[ContextPattern], ContextPattern]:
    def register(function: ContextPattern) -> ContextPattern:
        CONTEXT_PATTERNS[name] = function
        return function

    return register


def _fraction(value: Any, default: Fraction) -> Fraction:
    return default if value is None else Fraction(value)


def cell_hits(context: PatternContext, cell: str, step: Fraction):
    """
    Walk a looping rhythm cell across this slot.

    The cell is anchored to the section, so it keeps its place in the bar however
    the chords divide the section up. A chord change mid-cell does not restart it.

    Yields:
        (absolute start, duration, weight) for each hit inside the slot
    """
    hits, length = read_cell(cell)
    if not hits or length == 0:
        return
    period = length * step
    first_cycle = context.section_offset // period
    end = context.section_offset + context.dur
    cycle = first_cycle
    while cycle * period < end:
        for hit in hits:
            offset = cycle * period + hit.step * step
            if context.section_offset <= offset < end:
                start = context.start + offset - context.section_offset
                yield start, hit.steps * step, hit.weight
        cycle += 1


@context_pattern("grid")
def grid(context: PatternContext) -> list[Event]:
    """
    One sound on a step grid: the way to write drums.

    Params:
        cell: The rhythm, in the notation of `pypulang.rhythm`
        step: Beats per step (default 1/4, a sixteenth note)
        pitch: MIDI note to play (default 60)
        gate: Portion of each step the note sounds for (default 1/2)
    """
    step = _fraction(context.params.get("step"), Fraction(1, 4))
    pitch = int(context.params.get("pitch", 60)) + 12 * context.octave
    gate = _fraction(context.params.get("gate"), Fraction(1, 2))
    return [
        Event(pitch, start, dur * gate, scaled_velocity(context.velocity, weight))
        for start, dur, weight in cell_hits(context, context.params["cell"], step)
    ]


@context_pattern("hits")
def hits(context: PatternContext) -> list[Event]:
    """
    The whole voicing, on a rhythm: stabs, pads, comping you write out yourself.

    Params:
        cell: The rhythm. "-" holds a chord across steps.
        step: Beats per step (default 1/4)
        gate: Portion of each hit that sounds (default 1)
    """
    step = _fraction(context.params.get("step"), Fraction(1, 4))
    gate = _fraction(context.params.get("gate"), Fraction(1))
    events = []
    for start, dur, weight in cell_hits(context, context.params["cell"], step):
        velocity = scaled_velocity(context.velocity, weight)
        for pitch in context.pitches:
            events.append(Event(pitch + 12 * context.octave, start, dur * gate, velocity))
    return events


_DEGREE_SEMITONES = {
    "1": 0,
    "b2": 1,
    "2": 2,
    "b3": 3,
    "#2": 3,
    "4": 5,
    "#4": 6,
    "b5": 6,
    "#5": 8,
    "b6": 8,
    "6": 9,
    "bb7": 9,
    "b7": 10,
    "b9": 13,
    "9": 14,
    "#9": 15,
    "11": 17,
    "#11": 18,
    "b13": 20,
    "13": 21,
}


def degree_interval(token: str, shape: ChordShape) -> int:
    """
    Semitones above the root for a degree such as "3", "b7" or "9".

    "3", "5" and "7" mean the chord's own third, fifth and seventh, so one riff fits
    major and minor chords alike. Everything else is literal.

    A trailing "'" raises an octave and "," lowers one.
    """
    octave = token.count("'") - token.count(",")
    name = token.rstrip("',")
    if name in ("3", "5", "7"):
        function = {"3": ("3", "4", "2"), "5": ("5", "b5", "#5"), "7": ("7", "6")}[name]
        tone = shape.find(*function)
        fallback = {"3": 4, "5": 7, "7": 10}[name]
        base = tone.interval if tone is not None else fallback
    elif name in _DEGREE_SEMITONES:
        base = _DEGREE_SEMITONES[name]
    else:
        raise ValueError(f"Unknown degree {token!r}")
    return base + 12 * octave


@context_pattern("riff")
def riff(context: PatternContext) -> list[Event]:
    """
    A line written in chord degrees, so it follows the changes.

    Params:
        cell: The rhythm
        degrees: Space-separated degrees, one per hit, looping. "." rests that hit.
        step: Beats per step (default 1/4)
        base: MIDI pitch the root is placed nearest to (default 48)
        gate: Portion of each hit that sounds (default 1)
    """
    step = _fraction(context.params.get("step"), Fraction(1, 4))
    gate = _fraction(context.params.get("gate"), Fraction(1))
    degrees = context.params["degrees"].split()
    base = int(context.params.get("base", 48))
    shape = context.shape
    root = shape.bass if shape.bass is not None else shape.root
    anchor = base + ((root - base + 6) % 12) - 6
    events = []
    hits_in_cell, length = read_cell(context.params["cell"])
    per_cycle = len(hits_in_cell)
    period = length * step
    for start, dur, weight in cell_hits(context, context.params["cell"], step):
        offset = start - context.start + context.section_offset
        cycle = int(offset // period)
        within = (offset - cycle * period) / step
        index = next(i for i, h in enumerate(hits_in_cell) if h.step == within)
        token = degrees[(cycle * per_cycle + index) % len(degrees)]
        if token == ".":
            continue
        pitch = anchor + degree_interval(token, shape) + 12 * context.octave
        events.append(Event(pitch, start, dur * gate, scaled_velocity(context.velocity, weight)))
    return events
