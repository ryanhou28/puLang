"""
The `score` dialect: realized music, bar by bar.

A score starts life as `score.slot` ops, one per chord per part: "this pattern,
over this chord, with these pitches". Voicing passes rewrite the pitches while
they are still slots, so the decision stays visible as IR. `realize-patterns`
then expands each slot into `score.note` ops inside `score.bar` ops.

Beats are quarter notes from the start of the bar, counted from zero. A note may
ring past its bar: this level records music, and has no need of a notated tie.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from xdsl.dialects.builtin import ArrayAttr, DictionaryAttr, FloatAttr, IntegerAttr, StringAttr, i64
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
    ChordAttr,
    KeyAttr,
    MeterAttr,
    RationalAttr,
    float_attr,
    format_rational,
    parse_rational,
    to_attr,
)
from pypulang.ir.intent import Chord, Key, TimeSignature


@irdl_op_definition
class ScoreOp(IRDLOperation):
    """A realized piece: section markers, then parts."""

    name = "score.score"
    title = prop_def(StringAttr)
    tempo = prop_def(FloatAttr)
    key = prop_def(KeyAttr)
    meter = prop_def(MeterAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = "$title `tempo` $tempo `key` $key `meter` $meter attr-dict-with-keyword $body"

    def __init__(self, title: str, tempo: float, key: Key, meter: TimeSignature, ops: Sequence):
        super().__init__(
            properties={
                "title": StringAttr(title),
                "tempo": float_attr(tempo),
                "key": KeyAttr(key),
                "meter": MeterAttr(meter),
            },
            regions=[Region(Block(ops))],
        )

    def parts(self) -> list[PartOp]:
        return [op for op in self.body.block.ops if isinstance(op, PartOp)]

    def sections(self) -> list[SectionOp]:
        return [op for op in self.body.block.ops if isinstance(op, SectionOp)]

    def chords(self) -> list[ChordOp]:
        return [op for op in self.body.block.ops if isinstance(op, ChordOp)]


@irdl_op_definition
class SectionOp(IRDLOperation):
    """Where one occurrence of a section sits in the timeline."""

    name = "score.section"
    section = prop_def(StringAttr)
    occurrence = prop_def(IntegerAttr)
    start_bar = prop_def(IntegerAttr)
    bars = prop_def(IntegerAttr)
    start = prop_def(RationalAttr)
    key = prop_def(KeyAttr)
    meter = prop_def(MeterAttr)
    assembly_format = (
        "$section `occurrence` $occurrence `bar` $start_bar `bars` $bars `at` $start `key` $key "
        "`meter` $meter attr-dict"
    )

    def __init__(
        self,
        section: str,
        occurrence: int,
        start_bar: int,
        bars: int,
        start: Fraction,
        key: Key,
        meter: TimeSignature,
    ):
        super().__init__(
            properties={
                "section": StringAttr(section),
                "occurrence": IntegerAttr(occurrence, i64),
                "start_bar": IntegerAttr(start_bar, i64),
                "bars": IntegerAttr(bars, i64),
                "start": RationalAttr(start),
                "key": KeyAttr(key),
                "meter": MeterAttr(meter),
            }
        )

    @property
    def length(self) -> Fraction:
        return self.bars.value.data * self.meter.data.beats_per_bar

    @property
    def tag(self) -> str:
        return f"{self.section.data}#{self.occurrence.value.data}"


@irdl_op_definition
class ChordOp(IRDLOperation):
    """
    One chord in the piece's harmonic timeline.

    Slots carry a chord until they become notes, and then that knowledge would be
    gone. This keeps it, so analysis can ask what was sounding under any note.
    """

    name = "score.chord"
    chord = prop_def(ChordAttr)
    key = prop_def(KeyAttr)
    at = prop_def(RationalAttr)
    dur = prop_def(RationalAttr)
    assembly_format = "$chord `key` $key `at` $at `for` $dur attr-dict"

    def __init__(self, chord: Chord, key: Key, at: Fraction, dur: Fraction):
        super().__init__(
            properties={
                "chord": ChordAttr(chord),
                "key": KeyAttr(key),
                "at": RationalAttr(at),
                "dur": RationalAttr(dur),
            }
        )


@irdl_op_definition
class PartOp(IRDLOperation):
    """One track's music across the whole piece."""

    name = "score.part"
    part = prop_def(StringAttr)
    role = prop_def(StringAttr)
    instrument = prop_def(StringAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = "$part `role` $role `instrument` $instrument attr-dict-with-keyword $body"

    def __init__(self, part: str, role: str, instrument: str, ops: Sequence):
        super().__init__(
            properties={
                "part": StringAttr(part),
                "role": StringAttr(role),
                "instrument": StringAttr(instrument),
            },
            regions=[Region(Block(ops))],
        )

    def slots(self) -> list[SlotOp]:
        return [op for op in self.body.block.ops if isinstance(op, SlotOp)]

    def bars(self) -> list[BarOp]:
        return [op for op in self.body.block.ops if isinstance(op, BarOp)]


@irdl_op_definition
class SlotOp(IRDLOperation):
    """
    One chord's worth of a pattern on one part, not yet expanded into notes.

    `start` and `dur` are absolute quarter notes. `pitches` is the voicing the
    pattern will draw from, and it is what voicing passes rewrite.
    """

    name = "score.slot"
    kind = prop_def(StringAttr)
    chord = prop_def(ChordAttr)
    key = prop_def(KeyAttr)
    meter = prop_def(MeterAttr)
    start = prop_def(RationalAttr)
    dur = prop_def(RationalAttr)
    pitches = prop_def(ArrayAttr)
    params = prop_def(DictionaryAttr)
    section = prop_def(StringAttr)
    octave = prop_def(IntegerAttr)
    velocity = prop_def(IntegerAttr)
    voicing = opt_prop_def(StringAttr)
    next_chord = opt_prop_def(ChordAttr)
    assembly_format = (
        "$kind `chord` $chord `key` $key `meter` $meter `at` $start `for` $dur `pitches` $pitches "
        "`in` $section `octave` $octave `velocity` $velocity (`voicing` $voicing^)? "
        "(`next` $next_chord^)? `with` $params attr-dict"
    )

    def __init__(
        self,
        kind: str,
        chord: Chord,
        key: Key,
        meter: TimeSignature,
        start: Fraction,
        dur: Fraction,
        pitches: Sequence[int],
        params: dict[str, object],
        section: str,
        octave: int,
        velocity: int,
        voicing: str | None = None,
        next_chord: Chord | None = None,
    ):
        props: dict[str, Attribute] = {
            "kind": StringAttr(kind),
            "chord": ChordAttr(chord),
            "key": KeyAttr(key),
            "meter": MeterAttr(meter),
            "start": RationalAttr(start),
            "dur": RationalAttr(dur),
            "pitches": to_attr(list(pitches)),
            "params": to_attr(params),
            "section": StringAttr(section),
            "octave": IntegerAttr(octave, i64),
            "velocity": IntegerAttr(velocity, i64),
        }
        if voicing is not None:
            props["voicing"] = StringAttr(voicing)
        if next_chord is not None:
            props["next_chord"] = ChordAttr(next_chord)
        super().__init__(properties=props)

    def pitch_list(self) -> list[int]:
        return [p.value.data for p in self.pitches.data]

    def set_pitches(self, pitches: Sequence[int]) -> None:
        self.properties["pitches"] = to_attr(list(pitches))


@irdl_op_definition
class BarOp(IRDLOperation):
    """One bar of one part. `number` counts from 1 across the whole piece."""

    name = "score.bar"
    number = prop_def(IntegerAttr)
    start = prop_def(RationalAttr)
    meter = prop_def(MeterAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = "$number `at` $start `meter` $meter attr-dict-with-keyword $body"

    def __init__(self, number: int, start: Fraction, meter: TimeSignature, ops: Sequence = ()):
        super().__init__(
            properties={
                "number": IntegerAttr(number, i64),
                "start": RationalAttr(start),
                "meter": MeterAttr(meter),
            },
            regions=[Region(Block(ops))],
        )

    def notes(self) -> list[NoteOp]:
        return [op for op in self.body.block.ops if isinstance(op, NoteOp)]


@irdl_op_definition
class NoteOp(IRDLOperation):
    """
    A note with a name, a voice, and a place in the bar.

    Printed as `score.note "F#4" v1 at 3/2 for 1/2 vel 100`.
    """

    name = "score.note"
    pitch = prop_def(StringAttr)
    voice = prop_def(IntegerAttr)
    beat = prop_def(RationalAttr)
    dur = prop_def(RationalAttr)
    vel = prop_def(IntegerAttr)
    dynamic = opt_prop_def(StringAttr)
    articulation = opt_prop_def(StringAttr)

    def __init__(
        self,
        pitch: str,
        voice: int,
        beat: Fraction,
        dur: Fraction,
        vel: int,
        dynamic: str | None = None,
        articulation: str | None = None,
    ):
        props: dict[str, Attribute] = {
            "pitch": StringAttr(pitch),
            "voice": IntegerAttr(voice, i64),
            "beat": RationalAttr(beat),
            "dur": RationalAttr(dur),
            "vel": IntegerAttr(vel, i64),
        }
        if dynamic is not None:
            props["dynamic"] = StringAttr(dynamic)
        if articulation is not None:
            props["articulation"] = StringAttr(articulation)
        super().__init__(properties=props)

    def print(self, printer: Printer) -> None:
        printer.print_string(" ")
        printer.print_string_literal(self.pitch.data)
        printer.print_string(
            f" v{self.voice.value.data} at {format_rational(self.beat.data)}"
            f" for {format_rational(self.dur.data)} vel {self.vel.value.data}"
        )
        if self.dynamic is not None:
            printer.print_string(" dyn ")
            printer.print_string_literal(self.dynamic.data)
        if self.articulation is not None:
            printer.print_string(" art ")
            printer.print_string_literal(self.articulation.data)

    @classmethod
    def parse(cls, parser: Parser) -> NoteOp:
        pitch = parser.parse_str_literal()
        token = parser.parse_identifier()
        if not token.startswith("v"):
            parser.raise_error("expected a voice such as v0")
        voice = int(token[1:])
        parser.parse_keyword("at")
        beat = parse_rational(parser)
        parser.parse_keyword("for")
        dur = parse_rational(parser)
        parser.parse_keyword("vel")
        vel = parser.parse_integer(allow_boolean=False, allow_negative=False)
        dynamic = parser.parse_str_literal() if parser.parse_optional_keyword("dyn") else None
        articulation = parser.parse_str_literal() if parser.parse_optional_keyword("art") else None
        return cls(pitch, voice, beat, dur, vel, dynamic, articulation)


ScoreDialect = Dialect("score", [ScoreOp, SectionOp, ChordOp, PartOp, SlotOp, BarOp, NoteOp], [])
