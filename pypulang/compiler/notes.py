"""Placing notes into the bars of a `score.part`."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from pypulang.compiler.dialects import score
from pypulang.compiler.locs import in_section, note_place
from pypulang.compiler.spelling import spell
from pypulang.compiler.timeline import Bar, Timeline


@dataclass
class NoteRecord:
    """A note in absolute time, on its way into a bar."""

    pitch: int
    start: Fraction
    dur: Fraction
    vel: int
    articulation: str | None = None


def _bar_op(part: score.PartOp, bars: dict[int, score.BarOp], bar: Bar) -> score.BarOp:
    op = bars.get(bar.number)
    if op is None:
        op = score.BarOp(bar.number, bar.start, bar.meter)
        op.location = in_section(
            f"{bar.section}/{part.part.data}/{bar.in_section}", bar.section, bar.occurrence
        )
        part.body.block.add_op(op)
        bars[bar.number] = op
    return op


def add_notes(part: score.PartOp, timeline: Timeline, records: list[NoteRecord]) -> None:
    """
    Put notes into a part's bars and give each one its location.

    Notes starting together are numbered from the bottom as voices v0, v1, ...
    Drum parts name a lane by its pitch instead (d36), since a hi-hat is not the
    second voice of a kick and must keep its name when the kick drops out.
    """
    drums = part.role.data == "rhythm"
    bars = {op.number.value.data: op for op in part.bars()}

    onsets: dict[Fraction, list[NoteRecord]] = defaultdict(list)
    for record in records:
        onsets[record.start].append(record)

    seen: dict[tuple[str, int], int] = defaultdict(int)
    for start in sorted(onsets):
        bar = timeline.bar_at(start)
        beat = start - bar.start
        bar_op = _bar_op(part, bars, bar)
        for index, record in enumerate(sorted(onsets[start], key=lambda r: r.pitch)):
            voice = f"d{record.pitch}" if drums else f"v{index}"
            place = note_place(bar.section, part.part.data, bar.in_section, beat, voice)
            seen[(place, bar.occurrence)] += 1
            if seen[(place, bar.occurrence)] > 1:
                place = f"{place}~{seen[(place, bar.occurrence)] - 1}"
            note = score.NoteOp(
                pitch=spell(record.pitch, bar.key),
                voice=record.pitch if drums else index,
                beat=beat,
                dur=record.dur,
                vel=record.vel,
                articulation=record.articulation,
            )
            note.location = in_section(place, bar.section, bar.occurrence)
            bar_op.body.block.add_op(note)
