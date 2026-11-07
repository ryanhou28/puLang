"""Jazz and fusion: walking bass and comping."""

from __future__ import annotations

from fractions import Fraction

from pypulang.context_patterns import Event, PatternContext, context_pattern
from pypulang.harmony import ChordShape
from pypulang.rhythm import read_cell, scaled_velocity

# Eighth-note comping cells, sparse to busy. Two bars of comping should breathe, so
# the sparse ones lead: a pianist is mostly deciding where not to play.
COMP_CELLS = (
    "x.......",
    "...x....",
    "x..x....",
    "..x...x.",
    ".x....x.",
    "x.....x.",
    "x..x..x.",
    ".x..x..x",
)


def _in_range(pitch_class: int, near: int, low: int, high: int) -> int:
    """The pitch of a class closest to `near`, inside the range."""
    best = near + ((pitch_class - near + 6) % 12) - 6
    while best < low:
        best += 12
    while best > high:
        best -= 12
    return best


def _approach(target: int, rng) -> int:
    """A chromatic neighbour, or the fifth above: how a walking line sets up a root."""
    return target + rng.choice((-1, 1, 1, -1, 7 - 12))


def _steps_toward(start: int, end: int, count: int, tones: list[int]) -> list[int]:
    """`count` notes moving from `start` toward `end` through the given pitch classes."""
    pitches = []
    current = start
    direction = 1 if end >= start else -1
    for i in range(count):
        remaining = abs(end - current)
        stride = max(1, remaining // (count - i + 1))
        candidate = current + direction * stride
        for offset in range(0, 7):
            for sign in (1, -1):
                pitch = candidate + sign * offset
                if pitch % 12 in tones and pitch != current:
                    candidate = pitch
                    break
            else:
                continue
            break
        pitches.append(candidate)
        current = candidate
    return pitches


@context_pattern("walking_bass")
def walking_bass(context: PatternContext) -> list[Event]:
    """
    A quarter-note walking line.

    It lands on the root on the chord's first beat, moves through chord and scale
    tones, and spends its last beat approaching the next chord's root.

    Params:
        low: Lowest pitch (default 28, E1)
        high: Highest pitch (default 55, G3)
        centre: Where the line lives (default 40)
    """
    low = int(context.params.get("low", 28))
    high = int(context.params.get("high", 55))
    centre = int(context.params.get("centre", 40))
    rng = context.rng("walk")
    shape: ChordShape = context.shape
    bass_pc = shape.bass if shape.bass is not None else shape.root
    root = _in_range(bass_pc, centre + rng.randint(-3, 3), low, high)
    next_shape = context.next_shape
    next_pc = (
        bass_pc
        if next_shape is None
        else (next_shape.bass if next_shape.bass is not None else next_shape.root)
    )
    target = _in_range(next_pc, root, low, high)

    beats = int(context.dur)
    if beats <= 0:
        return []
    chord_tones = [shape.pitch_class(t) for t in shape.tones]
    tones = sorted(set(chord_tones) | set(context.scale_pcs()))

    if beats == 1:
        line = [root]
    else:
        middle = _steps_toward(root, target, beats - 2, tones) if beats > 2 else []
        line = [root, *middle, _approach(target, rng)]

    velocity = context.velocity
    events = []
    for index, pitch in enumerate(line):
        accent = 8 if index == 0 else (4 if index % 2 == 0 else 0)
        pitch = max(low, min(high, pitch)) + 12 * context.octave
        vel = max(1, min(127, velocity + accent + rng.randint(-5, 5)))
        events.append(Event(pitch, context.start + index, Fraction(19, 20), vel))
    return events


@context_pattern("comp")
def comp(context: PatternContext) -> list[Event]:
    """
    Piano-style comping from a library of rhythms.

    The rhythm changes bar by bar. A hit on the last eighth of a chord anticipates
    the next chord, played with that chord's voicing, which is what makes the time
    feel like it is pushing forward.

    Params:
        density: 0 to 1, how busy (default 1/2)
        short: Portion of an eighth a hit sounds for (default 3/2)
    """
    density = float(context.params.get("density", 0.5))
    short = Fraction(context.params.get("short", Fraction(3, 2)))
    step = Fraction(1, 2)
    cells = COMP_CELLS[: max(2, int(len(COMP_CELLS) * density) + 1)]

    events = []
    bar_beats = context.bar_beats
    end = context.section_offset + context.dur
    bar = context.section_offset // bar_beats
    while bar * bar_beats < end:
        rng = context.rng(f"bar{bar}")
        hits, length = read_cell(rng.choice(cells))
        for hit in hits:
            offset = bar * bar_beats + hit.step * step
            if hit.step * step >= bar_beats or not (context.section_offset <= offset < end):
                continue
            start = context.start + offset - context.section_offset
            anticipates = (
                context.next_pitches is not None and offset + step >= end and hit.step == length - 1
            )
            pitches = context.next_pitches if anticipates else context.pitches
            weight = hit.weight * Fraction(rng.randint(85, 110), 100)
            velocity = scaled_velocity(context.velocity, weight)
            for pitch in pitches:
                events.append(Event(pitch + 12 * context.octave, start, step * short, velocity))
        bar += 1
    return events
