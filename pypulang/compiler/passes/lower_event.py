"""
`lower-event-to-daw`: cut the event stream into tracks and clips, in ticks.

One clip per track per section occurrence, so a section a person moves or mutes in
the DAW is one object. Time becomes integer ticks here, and this is the only place
that can lose precision: anything finer than a tick is rounded and reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from xdsl.context import Context
from xdsl.dialects.builtin import ArrayAttr, ModuleOp, StringAttr
from xdsl.passes import ModulePass

from pypulang.compiler.dialects import daw, event
from pypulang.compiler.locs import loc_key

PPQ = 960


def warn(module: ModuleOp, message: str) -> None:
    """Record a compiler warning on the module, where it survives into printed IR."""
    existing = module.attributes.get("pulang.warnings")
    items = list(existing.data) if isinstance(existing, ArrayAttr) else []
    module.attributes["pulang.warnings"] = ArrayAttr([*items, StringAttr(message)])


def warnings_of(module: ModuleOp) -> list[str]:
    existing = module.attributes.get("pulang.warnings")
    return [s.data for s in existing.data] if isinstance(existing, ArrayAttr) else []


def ticks(value: Fraction) -> int:
    """Quarter notes to ticks, rounding to the nearest tick."""
    return round(value * PPQ)


def _section_of(note: event.NoteOp, sections: list[event.SectionOp]) -> event.SectionOp:
    tag = loc_key(note.location).partition("/")[0]
    for section in sections:
        if section.tag.data == tag:
            return section
    # Hand-written IR may carry no location. Fall back to where the note starts.
    start = note.start.data
    for section in sections:
        if section.at.data <= start < section.at.data + section.length.data:
            return section
    return sections[-1]


def _clips(
    track: event.TrackOp, sections: list[event.SectionOp]
) -> tuple[list[daw.ClipOp], int, int]:
    groups: dict[str, list[event.NoteOp]] = {}
    for note in track.notes():
        groups.setdefault(_section_of(note, sections).tag.data, []).append(note)

    inexact = 0
    clipped = 0
    clips = []
    for section in sections:
        tag = section.tag.data
        if tag not in groups:
            continue
        clip_start = ticks(section.at.data)
        clip_length = ticks(section.length.data)
        notes = []
        for note in groups[tag]:
            start_exact = note.start.data * PPQ
            dur_exact = note.dur.data * PPQ
            inexact += start_exact.denominator != 1 or dur_exact.denominator != 1
            start = max(round(start_exact) - clip_start, 0)
            dur = max(round(dur_exact), 1)
            if start >= clip_length:
                clipped += 1
                continue
            if start + dur > clip_length:
                clipped += 1
                dur = clip_length - start
            lowered = daw.NoteOp(
                max(0, min(127, note.pitch.value.data)),
                start,
                dur,
                max(0, min(127, note.vel.value.data)),
            )
            lowered.location = note.location
            notes.append(lowered)
        clip = daw.ClipOp(f"{tag}/{track.track.data}", clip_start, clip_length, notes)
        clip.location = section.location
        clips.append(clip)
    return clips, inexact, clipped


@dataclass(frozen=True)
class LowerEventToDaw(ModulePass):
    name = "lower-event-to-daw"

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        streams = [o for o in op.body.block.ops if isinstance(o, event.StreamOp)]
        if len(streams) != 1:
            raise ValueError(f"Expected one event.stream, found {len(streams)}")
        stream = streams[0]
        sections = stream.sections()

        ops: list = [daw.TempoOp(ticks(t.at.data), t.bpm.value.data) for t in stream.tempos()]
        last_meter = None
        for section in sections:
            meter = section.meter.data
            if meter != last_meter:
                ops.append(daw.MeterOp(ticks(section.at.data), meter.numerator, meter.denominator))
                last_meter = meter
            ops.append(daw.MarkerOp(ticks(section.at.data), section.tag.data))

        inexact = 0
        clipped = 0
        for track in stream.tracks():
            clips, track_inexact, track_clipped = _clips(track, sections)
            inexact += track_inexact
            clipped += track_clipped
            lowered = daw.TrackOp(track.track.data, track.role.data, clips)
            lowered.location = track.location
            ops.append(lowered)

        if inexact:
            warn(op, f"{inexact} note(s) needed rounding to {PPQ} ticks per quarter note")
        if clipped:
            warn(op, f"{clipped} note(s) ran past the end of their section and were cut")

        result = daw.ProjectOp(stream.title.data, PPQ, ops)
        result.location = stream.location
        op.body.block.detach_op(stream)
        op.body.block.add_op(result)
