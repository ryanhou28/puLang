"""`realize-patterns`: expand every `score.slot` into notes."""

from __future__ import annotations

from dataclasses import dataclass

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass

from pypulang.compiler.dialects import score
from pypulang.compiler.dialects.mus import from_attr
from pypulang.compiler.notes import NoteRecord, add_notes
from pypulang.compiler.timeline import Timeline
from pypulang.patterns import generate_pattern


def _slot_records(slot: score.SlotOp) -> list[NoteRecord]:
    events = generate_pattern(
        pattern_type=slot.kind.data,
        chord_pitches=slot.pitch_list(),
        duration=slot.dur.data,
        offset=slot.start.data,
        track_params={
            "octave_shift": slot.octave.value.data,
            "velocity": slot.velocity.value.data,
        },
        pattern_params=from_attr(slot.params),
    )
    return [NoteRecord(pitch, start, dur, vel) for pitch, start, dur, vel in events]


@dataclass(frozen=True)
class RealizePatterns(ModulePass):
    name = "realize-patterns"

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        for top in op.body.block.ops:
            if not isinstance(top, score.ScoreOp):
                continue
            timeline = Timeline(top.sections())
            for part in top.parts():
                slots = part.slots()
                records: list[NoteRecord] = []
                for slot in slots:
                    records.extend(_slot_records(slot))
                    part.body.block.detach_op(slot)
                add_notes(part, timeline, records)
                _sort_bars(part)


def _sort_bars(part: score.PartOp) -> None:
    bars = part.bars()
    for bar in bars:
        part.body.block.detach_op(bar)
    for bar in sorted(bars, key=lambda b: b.number.value.data):
        part.body.block.add_op(bar)
