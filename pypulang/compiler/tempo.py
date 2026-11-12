"""
The tempo map: where a song's tempo changes, and what time a beat falls at.

A section plays at its own tempo, or the piece's when it names none, so a section
after a ritardando is back "a tempo". Inside a section a ramp moves the tempo to a
new value (a ritardando or accelerando) and a hold plays some beats several times
as long (a fermata). kaiDAW's tempo changes are steps, so a ramp is written as a
step every half beat, each at the tempo of its middle, which keeps the ramp's
length right.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

RAMP_STEP = Fraction(1, 2)
# What kaiDAW's tempo map takes.
LOWEST_BPM, HIGHEST_BPM = 20, 300


def _tempo_at(points: list[tuple[Fraction, float]], at: Fraction) -> float:
    return [bpm for t, bpm in sorted(points, key=lambda p: p[0]) if t <= at][-1]


def section_points(
    start: Fraction,
    length: Fraction,
    base: float,
    changes: list[tuple[str, Fraction, Fraction, float]],
) -> list[tuple[Fraction, float]]:
    """
    One section occurrence's tempo points, in absolute beats.

    Ramps are laid out first, each from the tempo in force where it starts; then
    each hold stretches whatever tempo is under it, a ramp included, and the
    music picks up after it where it would have been.

    Args:
        start: Where the occurrence starts
        length: Its length in beats
        base: Its tempo
        changes: (kind, at, length, value) inside it, as `intent.tempo` holds them
    """
    for kind, *_ in changes:
        if kind not in ("ramp", "hold"):
            raise ValueError(f"No tempo change called {kind!r}; there are ramp and hold")
    points = [(start, base)]
    for _, at, span, value in sorted((c for c in changes if c[0] == "ramp"), key=lambda c: c[1]):
        begin = start + at
        end = min(start + at + span, start + length)
        current = _tempo_at(points, begin)
        points = [p for p in points if not begin <= p[0] < end]
        t = begin
        while t < end:
            middle = (t + min(t + RAMP_STEP, end)) / 2
            portion = float((middle - begin) / (end - begin))
            points.append((t, current + (value - current) * portion))
            t += RAMP_STEP
        points.append((end, value))
    for _, at, span, factor in (c for c in changes if c[0] == "hold"):
        begin = start + at
        end = min(start + at + span, start + length)
        before, after = _tempo_at(points, begin), _tempo_at(points, end)
        points = [p for p in points if p[0] not in (begin, end)] + [(begin, before), (end, after)]
        points = [(t, bpm / factor if begin <= t < end else bpm) for t, bpm in points]
    return points


def tidy(
    points: list[tuple[Fraction, float]], end: Fraction | None = None
) -> list[tuple[Fraction, float]]:
    """In order, one per beat position (the last given wins), without repeats or the end itself."""
    by_at: dict[Fraction, float] = {}
    for at, bpm in points:
        if end is None or at < end:
            by_at[at] = round(bpm, 3)
    result: list[tuple[Fraction, float]] = []
    for at in sorted(by_at):
        if not result or result[-1][1] != by_at[at]:
            result.append((at, by_at[at]))
    return result


def seconds_at(beat: Fraction | float, points: list[tuple[Any, float]]) -> float:
    """What time a beat falls at, through a tempo map of (beat, bpm) steps."""
    beat = Fraction(beat)
    seconds = 0.0
    for index, (at, bpm) in enumerate(points):
        at = Fraction(at)
        following = Fraction(points[index + 1][0]) if index + 1 < len(points) else None
        if beat <= at:
            break
        until = beat if following is None else min(beat, following)
        seconds += float(until - at) * 60.0 / bpm
    return seconds


def stream_points(module: Any) -> list[tuple[Fraction, float]]:
    """The tempo map of an `event` module."""
    from pypulang.compiler.dialects import event

    stream = next(o for o in module.body.block.ops if isinstance(o, event.StreamOp))
    return [(t.at.data, float(t.bpm.value.data)) for t in stream.tempos()]
