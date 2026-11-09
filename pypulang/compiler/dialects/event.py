"""
The `event` dialect: what happens, and when.

Pitches are MIDI numbers and times are exact quarter notes from the start of the
piece. Performance passes (swing, humanize, gate) run here, because they are
statements about time and loudness rather than about the notes' names.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from xdsl.dialects.builtin import ArrayAttr, FloatAttr, IntegerAttr, StringAttr, i64
from xdsl.ir import Attribute, Block, Dialect, Region
from xdsl.irdl import (
    IRDLOperation,
    irdl_op_definition,
    opt_prop_def,
    prop_def,
    region_def,
    traits_def,
)
from xdsl.parser import Parser
from xdsl.printer import Printer
from xdsl.traits import NoTerminator

from pypulang.compiler.dialects.mus import (
    MeterAttr,
    RationalAttr,
    float_attr,
    format_rational,
    parse_rational,
    to_attr,
)
from pypulang.ir.intent import TimeSignature


@irdl_op_definition
class StreamOp(IRDLOperation):
    """A whole piece as timed events."""

    name = "event.stream"
    title = prop_def(StringAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = "$title attr-dict-with-keyword $body"

    def __init__(self, title: str, ops: Sequence):
        super().__init__(properties={"title": StringAttr(title)}, regions=[Region(Block(ops))])

    def tracks(self) -> list[TrackOp]:
        return [op for op in self.body.block.ops if isinstance(op, TrackOp)]

    def sections(self) -> list[SectionOp]:
        return [op for op in self.body.block.ops if isinstance(op, SectionOp)]

    def tempos(self) -> list[TempoOp]:
        return [op for op in self.body.block.ops if isinstance(op, TempoOp)]


@irdl_op_definition
class TempoOp(IRDLOperation):
    name = "event.tempo"
    at = prop_def(RationalAttr)
    bpm = prop_def(FloatAttr)
    assembly_format = "$at `bpm` $bpm attr-dict"

    def __init__(self, at: Fraction, bpm: float):
        super().__init__(properties={"at": RationalAttr(at), "bpm": float_attr(bpm)})


@irdl_op_definition
class SectionOp(IRDLOperation):
    """One occurrence of a section. Clips are cut along these."""

    name = "event.section"
    tag = prop_def(StringAttr)
    at = prop_def(RationalAttr)
    length = prop_def(RationalAttr)
    meter = prop_def(MeterAttr)
    assembly_format = "$tag `at` $at `for` $length `meter` $meter attr-dict"

    def __init__(self, tag: str, at: Fraction, length: Fraction, meter: TimeSignature):
        super().__init__(
            properties={
                "tag": StringAttr(tag),
                "at": RationalAttr(at),
                "length": RationalAttr(length),
                "meter": MeterAttr(meter),
            }
        )


@irdl_op_definition
class TrackOp(IRDLOperation):
    name = "event.track"
    track = prop_def(StringAttr)
    role = prop_def(StringAttr)
    instrument = prop_def(StringAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = "$track `role` $role `instrument` $instrument attr-dict-with-keyword $body"

    def __init__(self, track: str, role: str, instrument: str, ops: Sequence):
        super().__init__(
            properties={
                "track": StringAttr(track),
                "role": StringAttr(role),
                "instrument": StringAttr(instrument),
            },
            regions=[Region(Block(ops))],
        )

    def notes(self) -> list[NoteOp]:
        return [op for op in self.body.block.ops if isinstance(op, NoteOp)]

    def curves(self) -> list[CurveOp]:
        return [op for op in self.body.block.ops if isinstance(op, CurveOp)]

    def audio(self) -> list[AudioOp]:
        return [op for op in self.body.block.ops if isinstance(op, AudioOp)]


@irdl_op_definition
class NoteOp(IRDLOperation):
    """Printed as `event.note 60 at 7/2 for 1/2 vel 100`."""

    name = "event.note"
    pitch = prop_def(IntegerAttr)
    start = prop_def(RationalAttr)
    dur = prop_def(RationalAttr)
    vel = prop_def(IntegerAttr)

    def __init__(self, pitch: int, start: Fraction, dur: Fraction, vel: int):
        super().__init__(
            properties={
                "pitch": IntegerAttr(pitch, i64),
                "start": RationalAttr(start),
                "dur": RationalAttr(dur),
                "vel": IntegerAttr(vel, i64),
            }
        )

    def print(self, printer: Printer) -> None:
        printer.print_string(
            f" {self.pitch.value.data} at {format_rational(self.start.data)}"
            f" for {format_rational(self.dur.data)} vel {self.vel.value.data}"
        )

    @classmethod
    def parse(cls, parser: Parser) -> NoteOp:
        pitch = parser.parse_integer(allow_boolean=False, allow_negative=False)
        parser.parse_keyword("at")
        start = parse_rational(parser)
        parser.parse_keyword("for")
        dur = parse_rational(parser)
        parser.parse_keyword("vel")
        vel = parser.parse_integer(allow_boolean=False, allow_negative=False)
        return cls(pitch, start, dur, vel)


@irdl_op_definition
class CurveOp(IRDLOperation):
    """
    A parameter moving over time on one track.

    `target` is "<device>.<parameter>", resolved against the track's rack when
    the piece reaches a DAW. `points` alternates time and value (0..1).

    The device `midi` is not a plugin: "midi.pitchbend", "midi.pressure" and
    "midi.cc1" to "midi.cc127" are controller lanes, which travel inside the clips
    with the notes instead of as automation.
    """

    name = "event.curve"
    target = prop_def(StringAttr)
    points = prop_def(ArrayAttr)
    assembly_format = "$target $points attr-dict"

    def __init__(self, target: str, points: Sequence[tuple[Fraction, Fraction]]):
        flat: list[Fraction] = []
        for at, value in points:
            flat.extend((Fraction(at), Fraction(value)))
        super().__init__(properties={"target": StringAttr(target), "points": to_attr(flat)})

    def point_list(self) -> list[tuple[Fraction, Fraction]]:
        values = [a.data for a in self.points.data]
        return list(zip(values[0::2], values[1::2], strict=True))


@irdl_op_definition
class AudioOp(IRDLOperation):
    """
    An audio file played on a track from `start`, in beats from the piece's start.

    `file` is a path to an audio file, relative to the song. `offset` is seconds into
    the file and `gain` decibels; `length` is absent for "to the end of the file".
    """

    name = "event.audio"
    file = prop_def(StringAttr)
    start = prop_def(RationalAttr)
    length = opt_prop_def(RationalAttr)
    offset = prop_def(FloatAttr)
    gain = prop_def(FloatAttr)
    assembly_format = "$file `at` $start (`for` $length^)? `offset` $offset `gain` $gain attr-dict"

    def __init__(
        self,
        file: str,
        start: Fraction,
        length: Fraction | None = None,
        offset: float = 0.0,
        gain: float = 0.0,
    ):
        props: dict[str, Attribute] = {
            "file": StringAttr(file),
            "start": RationalAttr(Fraction(start)),
            "offset": float_attr(offset),
            "gain": float_attr(gain),
        }
        if length is not None:
            props["length"] = RationalAttr(Fraction(length))
        super().__init__(properties=props)


EventDialect = Dialect(
    "event", [StreamOp, TempoOp, SectionOp, TrackOp, NoteOp, CurveOp, AudioOp], []
)
