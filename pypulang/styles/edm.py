"""Electronic production: the patterns a drop is built from."""

from __future__ import annotations

from fractions import Fraction

from pypulang.context_patterns import Event, PatternContext, context_pattern


@context_pattern("snare_roll")
def snare_roll(context: PatternContext) -> list[Event]:
    """
    A build: hits that speed up and get louder across a whole section.

    The roll is laid out against the section, so chords changing underneath it do
    not restart it. Each chord's slot plays whichever hits fall inside it.

    Params:
        beats: Length of the roll (default: the section, if `bars` is not given)
        bars: Length of the roll in bars
        pitch: MIDI note (default 60)
        rates: Beats between hits for each equal part of the roll
            (default 1, 1/2, 1/4, 1/8)
    """
    pitch = int(context.params.get("pitch", 60)) + 12 * context.octave
    rates = [Fraction(r) for r in context.params.get("rates", ["1", "1/2", "1/4", "1/8"])]
    total = Fraction(context.params.get("beats", context.params.get("bars", 8) * context.bar_beats))
    span = total / len(rates)
    end = context.section_offset + context.dur

    events = []
    position = Fraction(0)
    for index, rate in enumerate(rates):
        stop = span * (index + 1)
        while position < stop:
            if context.section_offset <= position < end:
                progress = position / total
                strength = Fraction(2, 5) + progress * Fraction(3, 5)
                velocity = max(1, min(127, int(context.velocity * strength)))
                start = context.start + position - context.section_offset
                events.append(Event(pitch, start, rate / 2, velocity))
            position += rate
    return events
