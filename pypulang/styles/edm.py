"""Electronic production: sweeps and the patterns a drop is built from."""

from __future__ import annotations

from fractions import Fraction

from pypulang.context_patterns import Event, PatternContext, context_pattern


@context_pattern("snare_roll")
def snare_roll(context: PatternContext) -> list[Event]:
    """
    A build: hits that double in speed, rising in velocity, over the whole slot.

    Params:
        pitch: MIDI note (default 60)
        rates: Beats between hits for each quarter of the roll
            (default [1, 1/2, 1/4, 1/8])
    """
    pitch = int(context.params.get("pitch", 60)) + 12 * context.octave
    rates = [Fraction(r) for r in context.params.get("rates", ["1", "1/2", "1/4", "1/8"])]
    span = context.dur / len(rates)
    events = []
    position = Fraction(0)
    for index, rate in enumerate(rates):
        end = span * (index + 1)
        while position < end:
            progress = position / context.dur
            velocity = max(
                1, min(127, int(context.velocity * (Fraction(2, 5) + progress * Fraction(3, 5))))
            )
            events.append(Event(pitch, context.start + position, rate / 2, velocity))
            position += rate
    return events
