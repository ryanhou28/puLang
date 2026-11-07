"""The bars of a piece, derived from its `score.section` markers."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction

from pypulang.compiler.dialects import score
from pypulang.ir.intent import Key, TimeSignature


@dataclass(frozen=True)
class Bar:
    number: int  # Across the whole piece, from 1
    start: Fraction
    meter: TimeSignature
    section: str
    occurrence: int
    in_section: int  # Within its section, from 1
    key: Key


class Timeline:
    """Finds the bar a moment falls in. Times past the end land in the last bar."""

    def __init__(self, sections: list[score.SectionOp]):
        self.bars: list[Bar] = []
        for op in sections:
            meter = op.meter.data
            start = op.start.data
            for i in range(op.bars.value.data):
                self.bars.append(
                    Bar(
                        number=op.start_bar.value.data + i,
                        start=start + i * meter.beats_per_bar,
                        meter=meter,
                        section=op.section.data,
                        occurrence=op.occurrence.value.data,
                        in_section=i + 1,
                        key=op.key.data,
                    )
                )
        self._starts = [b.start for b in self.bars]

    def bar_at(self, time: Fraction) -> Bar:
        index = bisect_right(self._starts, time) - 1
        return self.bars[max(index, 0)]
