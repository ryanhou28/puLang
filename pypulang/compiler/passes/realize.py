"""`realize-patterns`: expand every `score.slot` into notes."""

from __future__ import annotations

from dataclasses import dataclass

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass

import pypulang.styles  # noqa: F401  (registers the style patterns)
from pypulang.compiler.dialects import score
from pypulang.compiler.dialects.mus import from_attr
from pypulang.compiler.locs import loc_key
from pypulang.compiler.notes import NoteRecord, add_notes
from pypulang.compiler.timeline import Timeline
from pypulang.context_patterns import CONTEXT_PATTERNS, PatternContext
from pypulang.patterns import generate_pattern


def _slot_records(
    slot: score.SlotOp, following: score.SlotOp | None, timeline: Timeline
) -> list[NoteRecord]:
    """A slot's notes, less any that start where a drum fill has the slot rest."""
    params = from_attr(slot.params)
    silence = params.pop("silence", None)
    records = _pattern_records(slot, following, timeline, params)
    if not silence:
        return records
    return [r for r in records if not any(a <= r.start < b for a, b in silence)]


def _pattern_records(
    slot: score.SlotOp, following: score.SlotOp | None, timeline: Timeline, params: dict
) -> list[NoteRecord]:
    if slot.kind.data in CONTEXT_PATTERNS:
        bar = timeline.bar_at(slot.start.data)
        section_start = bar.start - (bar.in_section - 1) * bar.meter.beats_per_bar
        context = PatternContext(
            pitches=slot.pitch_list(),
            next_pitches=following.pitch_list() if following is not None else None,
            chord=slot.chord.data,
            next_chord=slot.next_chord.data if slot.next_chord is not None else None,
            key=slot.key.data,
            meter=slot.meter.data,
            start=slot.start.data,
            dur=slot.dur.data,
            section_offset=slot.start.data - section_start,
            params=params,
            octave=slot.octave.value.data,
            velocity=slot.velocity.value.data,
            seed=loc_key(slot.location),
        )
        return [
            NoteRecord(e.pitch, e.start, e.dur, e.vel, e.articulation)
            for e in CONTEXT_PATTERNS[slot.kind.data](context)
        ]
    events = generate_pattern(
        pattern_type=slot.kind.data,
        chord_pitches=slot.pitch_list(),
        duration=slot.dur.data,
        offset=slot.start.data,
        track_params={
            "octave_shift": slot.octave.value.data,
            "velocity": slot.velocity.value.data,
        },
        pattern_params=params,
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
                for index, slot in enumerate(slots):
                    following = slots[index + 1] if index + 1 < len(slots) else None
                    records.extend(_slot_records(slot, following, timeline))
                for slot in slots:
                    part.body.block.detach_op(slot)
                add_notes(part, timeline, records)
                _sort_bars(part)


def _sort_bars(part: score.PartOp) -> None:
    bars = part.bars()
    for bar in bars:
        part.body.block.detach_op(bar)
    for bar in sorted(bars, key=lambda b: b.number.value.data):
        part.body.block.add_op(bar)
