"""
The `intent` dialect: what the composer wants.

Harmony is an SSA value, so a track says which chords it follows and a pass that
rewrites the harmony reaches every track that uses it.

    intent.piece "song" tempo 120 key "G major" meter 4/4 {
      intent.section "verse" bars 8 {
        %0 = intent.harmony ...
        intent.track "bass" role "bass" {
          intent.pattern "root_eighths" over %0 ...
        }
      }
    }
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from xdsl.dialects.builtin import ArrayAttr, DictionaryAttr, FloatAttr, IntegerAttr, StringAttr, i64
from xdsl.ir import (
    Attribute,
    Block,
    Dialect,
    ParametrizedAttribute,
    Region,
    SSAValue,
    TypeAttribute,
)
from xdsl.irdl import (
    IRDLOperation,
    irdl_attr_definition,
    irdl_op_definition,
    operand_def,
    opt_prop_def,
    prop_def,
    region_def,
    result_def,
    traits_def,
)
from xdsl.traits import NoTerminator

from pypulang.compiler.dialects.mus import (
    ChordAttr,
    KeyAttr,
    MeterAttr,
    RationalAttr,
    float_attr,
    to_attr,
)
from pypulang.ir.intent import Chord, Key, TimeSignature


@irdl_attr_definition
class HarmonyType(ParametrizedAttribute, TypeAttribute):
    """The type of a chord progression value."""

    name = "intent.harmony"


@irdl_op_definition
class PieceOp(IRDLOperation):
    """A whole piece. Its body holds sections; `form` orders them when present."""

    name = "intent.piece"
    title = prop_def(StringAttr)
    tempo = prop_def(FloatAttr)
    key = prop_def(KeyAttr)
    meter = prop_def(MeterAttr)
    form = opt_prop_def(ArrayAttr[StringAttr])
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = "$title `tempo` $tempo `key` $key `meter` $meter (`form` $form^)? attr-dict-with-keyword $body"

    def __init__(
        self,
        title: str,
        tempo: float,
        key: Key,
        meter: TimeSignature,
        form: Sequence[str] | None,
        ops: Sequence[IRDLOperation],
    ):
        props: dict[str, Attribute] = {
            "title": StringAttr(title),
            "tempo": float_attr(tempo),
            "key": KeyAttr(key),
            "meter": MeterAttr(meter),
        }
        if form is not None:
            props["form"] = ArrayAttr([StringAttr(s) for s in form])
        super().__init__(properties=props, regions=[Region(Block(ops))])

    def sections(self) -> list[SectionOp]:
        return [op for op in self.body.block.ops if isinstance(op, SectionOp)]


@irdl_op_definition
class SectionOp(IRDLOperation):
    """A formal unit. `key` and `meter` override the piece when present."""

    name = "intent.section"
    section = prop_def(StringAttr)
    bars = prop_def(IntegerAttr)
    key = opt_prop_def(KeyAttr)
    meter = opt_prop_def(MeterAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = (
        "$section `bars` $bars (`key` $key^)? (`meter` $meter^)? attr-dict-with-keyword $body"
    )

    def __init__(
        self,
        section: str,
        bars: int,
        key: Key | None,
        meter: TimeSignature | None,
        ops: Sequence[IRDLOperation],
    ):
        props: dict[str, Attribute] = {
            "section": StringAttr(section),
            "bars": IntegerAttr(bars, i64),
        }
        if key is not None:
            props["key"] = KeyAttr(key)
        if meter is not None:
            props["meter"] = MeterAttr(meter)
        super().__init__(properties=props, regions=[Region(Block(ops))])

    def harmony(self) -> HarmonyOp | None:
        for op in self.body.block.ops:
            if isinstance(op, HarmonyOp):
                return op
        return None

    def tracks(self) -> list[TrackOp]:
        return [op for op in self.body.block.ops if isinstance(op, TrackOp)]

    def curves(self) -> list[CurveOp]:
        return [op for op in self.body.block.ops if isinstance(op, CurveOp)]

    def audio(self) -> list[AudioOp]:
        return [op for op in self.body.block.ops if isinstance(op, AudioOp)]


@irdl_op_definition
class HarmonyOp(IRDLOperation):
    """A chord progression. `unit` says whether durations are bars or beats."""

    name = "intent.harmony"
    chords = prop_def(ArrayAttr[ChordAttr])
    durations = prop_def(ArrayAttr[RationalAttr])
    unit = prop_def(StringAttr)
    result = result_def(HarmonyType)
    assembly_format = "$chords `for` $durations `in` $unit attr-dict `:` type($result)"

    def __init__(self, chords: Sequence[Chord], durations: Sequence[Fraction], unit: str):
        super().__init__(
            properties={
                "chords": ArrayAttr([ChordAttr(c) for c in chords]),
                "durations": ArrayAttr([RationalAttr(d) for d in durations]),
                "unit": StringAttr(unit),
            },
            result_types=[HarmonyType()],
        )

    def changes(self) -> list[tuple[Chord, Fraction]]:
        return [
            (c.data, d.data) for c, d in zip(self.chords.data, self.durations.data, strict=True)
        ]


@irdl_op_definition
class TrackOp(IRDLOperation):
    """One part in a section. Its body is a pattern or literal notes."""

    name = "intent.track"
    track = prop_def(StringAttr)
    role = prop_def(StringAttr)
    instrument = prop_def(StringAttr)
    octave = prop_def(IntegerAttr)
    velocity = prop_def(IntegerAttr)
    muted = prop_def(IntegerAttr)
    voicing = opt_prop_def(StringAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = (
        "$track `role` $role `instrument` $instrument `octave` $octave `velocity` $velocity "
        "`muted` $muted (`voicing` $voicing^)? attr-dict-with-keyword $body"
    )

    def __init__(
        self,
        track: str,
        role: str,
        instrument: str,
        octave: int,
        velocity: int,
        muted: bool,
        voicing: str | None,
        ops: Sequence[IRDLOperation],
    ):
        props: dict[str, Attribute] = {
            "track": StringAttr(track),
            "role": StringAttr(role),
            "instrument": StringAttr(instrument),
            "octave": IntegerAttr(octave, i64),
            "velocity": IntegerAttr(velocity, i64),
            "muted": IntegerAttr(int(muted), i64),
        }
        if voicing is not None:
            props["voicing"] = StringAttr(voicing)
        super().__init__(properties=props, regions=[Region(Block(ops))])


@irdl_op_definition
class PatternOp(IRDLOperation):
    """A generator that makes notes from the harmony it is given."""

    name = "intent.pattern"
    kind = prop_def(StringAttr)
    params = prop_def(DictionaryAttr)
    harmony = operand_def(HarmonyType)
    assembly_format = "$kind `over` $harmony `with` $params attr-dict `:` type($harmony)"

    def __init__(self, kind: str, harmony: SSAValue, params: dict[str, object]):
        super().__init__(
            operands=[harmony],
            properties={"kind": StringAttr(kind), "params": to_attr(params)},
        )


@irdl_op_definition
class NotesOp(IRDLOperation):
    """Literal notes: the escape hatch from patterns."""

    name = "intent.notes"
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = "attr-dict-with-keyword $body"

    def __init__(self, ops: Sequence[IRDLOperation]):
        super().__init__(regions=[Region(Block(ops))])


@irdl_op_definition
class NoteOp(IRDLOperation):
    """One literal note, placed from the start of its section."""

    name = "intent.note"
    pitch = prop_def(IntegerAttr)
    offset = prop_def(RationalAttr)
    dur = prop_def(RationalAttr)
    vel = opt_prop_def(IntegerAttr)
    art = opt_prop_def(StringAttr)
    assembly_format = "$pitch `at` $offset `for` $dur (`vel` $vel^)? (`art` $art^)? attr-dict"

    def __init__(
        self,
        pitch: int,
        offset: Fraction,
        dur: Fraction,
        vel: int | None,
        art: str | None = None,
    ):
        props: dict[str, Attribute] = {
            "pitch": IntegerAttr(pitch, i64),
            "offset": RationalAttr(offset),
            "dur": RationalAttr(dur),
        }
        if vel is not None:
            props["vel"] = IntegerAttr(vel, i64)
        if art is not None:
            props["art"] = StringAttr(art)
        super().__init__(properties=props)


@irdl_op_definition
class CurveOp(IRDLOperation):
    """
    A parameter moving during a section.

    `target` is "<device>.<parameter>". `points` alternates beats from the section
    start and a value from 0 to 1.
    """

    name = "intent.curve"
    track = prop_def(StringAttr)
    target = prop_def(StringAttr)
    points = prop_def(ArrayAttr)
    assembly_format = "$track `target` $target $points attr-dict"

    def __init__(self, track: str, target: str, points: Sequence[tuple[Fraction, Fraction]]):
        flat: list[Fraction] = []
        for at, value in points:
            flat.extend((Fraction(at), Fraction(value)))
        super().__init__(
            properties={
                "track": StringAttr(track),
                "target": StringAttr(target),
                "points": to_attr(flat),
            }
        )

    def point_list(self) -> list[tuple[Fraction, Fraction]]:
        values = [a.data for a in self.points.data]
        return list(zip(values[0::2], values[1::2], strict=True))


@irdl_op_definition
class AudioOp(IRDLOperation):
    """
    An audio file played on a track during a section, `at` beats from its start.

    `file` is a path to an audio file, relative to the song. `offset` is seconds into
    the file and `gain` decibels; `length` is absent for "to the end of the file".
    """

    name = "intent.audio"
    track = prop_def(StringAttr)
    file = prop_def(StringAttr)
    at = prop_def(RationalAttr)
    length = opt_prop_def(RationalAttr)
    offset = prop_def(FloatAttr)
    gain = prop_def(FloatAttr)
    assembly_format = (
        "$track $file `at` $at (`for` $length^)? `offset` $offset `gain` $gain attr-dict"
    )

    def __init__(
        self,
        track: str,
        file: str,
        at: Fraction,
        length: Fraction | None = None,
        offset: float = 0.0,
        gain: float = 0.0,
    ):
        props: dict[str, Attribute] = {
            "track": StringAttr(track),
            "file": StringAttr(file),
            "at": RationalAttr(Fraction(at)),
            "offset": float_attr(offset),
            "gain": float_attr(gain),
        }
        if length is not None:
            props["length"] = RationalAttr(Fraction(length))
        super().__init__(properties=props)


IntentDialect = Dialect(
    "intent",
    [PieceOp, SectionOp, HarmonyOp, TrackOp, PatternOp, NotesOp, NoteOp, CurveOp, AudioOp],
    [HarmonyType],
)
