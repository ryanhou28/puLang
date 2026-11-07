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


def _available_tones(context: PatternContext) -> list[int]:
    """Pitch classes for a line over this chord: its tones first, then its scale."""
    shape = context.shape
    chord_pcs = [shape.pitch_class(t) for t in shape.tones]
    avoid = {(shape.root + 5) % 12} if shape.find("3") is not None else set()
    scale = [pc for pc in context.scale_pcs() if pc not in chord_pcs and pc not in avoid]
    return chord_pcs + scale


def _nearest(pitch: int, pitch_classes: list[int], direction: int) -> int:
    """The closest pitch in these classes, strictly above or below `pitch`."""
    for step in range(1, 13):
        candidate = pitch + direction * step
        if candidate % 12 in pitch_classes:
            return candidate
    return pitch


@context_pattern("solo_line")
def solo_line(context: PatternContext) -> list[Event]:
    """
    An improvised-sounding line: eighth notes that outline the changes.

    Strong beats land on chord tones and weak ones step through the scale. The
    line turns around at the edges of its register, plays in phrases with rests
    between them, and ends each phrase on a longer note.

    Params:
        low: Lowest pitch (default 62)
        high: Highest pitch (default 86)
        phrase: Bars in a phrase (default 2)
        rest: Portion of phrases that are rests (default 1/4)
    """
    low = int(context.params.get("low", 62))
    high = int(context.params.get("high", 86))
    phrase_bars = int(context.params.get("phrase", 2))
    rest = float(context.params.get("rest", 0.25))
    shape = context.shape
    chord_pcs = [shape.pitch_class(t) for t in shape.tones if t.function != "1"] or [shape.root]
    tones = _available_tones(context)

    step = Fraction(1, 2)
    bar_beats = context.bar_beats
    phrase_beats = bar_beats * phrase_bars
    end = context.section_offset + context.dur
    offset = (context.section_offset // step) * step
    if offset < context.section_offset:
        offset += step

    events = []
    while offset < end:
        phrase = offset // phrase_beats
        rng = context.rng(f"phrase{phrase}")
        into_phrase = offset - phrase * phrase_beats
        if rng.random() < rest or into_phrase >= phrase_beats - 1:
            offset += step
            continue

        # Each phrase has its own shape: where it starts, and which way it heads.
        position = rng.randint(low + 6, high - 6)
        direction = rng.choice((-1, 1))
        walk = Fraction(0)
        while walk < into_phrase:
            walked = context.rng(f"walk{phrase}:{walk}")
            position += direction * walked.randint(1, 3)
            if position >= high - 2 or position <= low + 2:
                direction = -direction
            walk += step

        strong = offset % 1 == 0
        pool = chord_pcs if strong else tones
        pitch = _nearest(position, pool, direction)
        pitch = max(low, min(high, pitch))
        last_in_phrase = into_phrase + step >= phrase_beats - 1
        length = Fraction(1) if last_in_phrase else step * Fraction(9, 10)
        velocity = (
            context.velocity + (6 if strong else -4) + context.rng(f"v{offset}").randint(-6, 6)
        )
        events.append(
            Event(
                pitch,
                context.start + offset - context.section_offset,
                length,
                max(1, min(127, velocity)),
            )
        )
        offset += step
    return events
