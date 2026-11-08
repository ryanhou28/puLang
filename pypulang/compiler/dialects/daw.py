"""
The `daw` dialect: the project a DAW should hold.

This is the target of the compiler. Its vocabulary is a DAW's own: tracks, clips,
notes in integer ticks, plugin chains, automation. Nothing here knows what a
chord is. A kaiDAW client diffs this module against the project and sends the
difference as one transaction.
"""

from __future__ import annotations

from collections.abc import Sequence

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

from pypulang.compiler.dialects.mus import float_attr, to_attr


@irdl_op_definition
class ProjectOp(IRDLOperation):
    name = "daw.project"
    title = prop_def(StringAttr)
    ppq = prop_def(IntegerAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = "$title `ppq` $ppq attr-dict-with-keyword $body"

    def __init__(self, title: str, ppq: int, ops: Sequence):
        super().__init__(
            properties={"title": StringAttr(title), "ppq": IntegerAttr(ppq, i64)},
            regions=[Region(Block(ops))],
        )

    def tracks(self) -> list[TrackOp]:
        return [op for op in self.body.block.ops if isinstance(op, TrackOp)]

    def tempos(self) -> list[TempoOp]:
        return [op for op in self.body.block.ops if isinstance(op, TempoOp)]

    def meters(self) -> list[MeterOp]:
        return [op for op in self.body.block.ops if isinstance(op, MeterOp)]

    def markers(self) -> list[MarkerOp]:
        return [op for op in self.body.block.ops if isinstance(op, MarkerOp)]


@irdl_op_definition
class TempoOp(IRDLOperation):
    name = "daw.tempo"
    at = prop_def(IntegerAttr)
    bpm = prop_def(FloatAttr)
    assembly_format = "$at `bpm` $bpm attr-dict"

    def __init__(self, at: int, bpm: float):
        super().__init__(properties={"at": IntegerAttr(at, i64), "bpm": float_attr(bpm)})


@irdl_op_definition
class MeterOp(IRDLOperation):
    """A time signature change, which kaiDAW takes as part of its tempo map."""

    name = "daw.meter"
    at = prop_def(IntegerAttr)
    numerator = prop_def(IntegerAttr)
    denominator = prop_def(IntegerAttr)
    assembly_format = "$at `sig` $numerator `over` $denominator attr-dict"

    def __init__(self, at: int, numerator: int, denominator: int):
        super().__init__(
            properties={
                "at": IntegerAttr(at, i64),
                "numerator": IntegerAttr(numerator, i64),
                "denominator": IntegerAttr(denominator, i64),
            }
        )


@irdl_op_definition
class MarkerOp(IRDLOperation):
    """A named place in the timeline: a section's start, sent as a kaiDAW marker."""

    name = "daw.marker"
    at = prop_def(IntegerAttr)
    label = prop_def(StringAttr)
    assembly_format = "$at $label attr-dict"

    def __init__(self, at: int, label: str):
        super().__init__(properties={"at": IntegerAttr(at, i64), "label": StringAttr(label)})


@irdl_op_definition
class TrackOp(IRDLOperation):
    name = "daw.track"
    track = prop_def(StringAttr)
    role = prop_def(StringAttr)
    volume = opt_prop_def(FloatAttr)
    pan = opt_prop_def(FloatAttr)
    color = opt_prop_def(StringAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = (
        "$track `role` $role (`volume` $volume^)? (`pan` $pan^)? (`color` $color^)? "
        "attr-dict-with-keyword $body"
    )

    def __init__(
        self,
        track: str,
        role: str,
        ops: Sequence,
        volume: float | None = None,
        pan: float | None = None,
        color: str | None = None,
    ):
        props: dict[str, Attribute] = {"track": StringAttr(track), "role": StringAttr(role)}
        if volume is not None:
            props["volume"] = float_attr(volume)
        if pan is not None:
            props["pan"] = float_attr(pan)
        if color is not None:
            props["color"] = StringAttr(color)
        super().__init__(properties=props, regions=[Region(Block(ops))])

    def clips(self) -> list[ClipOp]:
        return [op for op in self.body.block.ops if isinstance(op, ClipOp)]

    def plugins(self) -> list[PluginOp]:
        return [op for op in self.body.block.ops if isinstance(op, PluginOp)]

    def automations(self) -> list[AutomationOp]:
        return [op for op in self.body.block.ops if isinstance(op, AutomationOp)]

    def sends(self) -> list[SendOp]:
        return [op for op in self.body.block.ops if isinstance(op, SendOp)]


@irdl_op_definition
class RackOp(IRDLOperation):
    """
    How a track sounds.

    A rack is already in the target's vocabulary, so it is written in this dialect
    from the start and rides through the higher levels untouched. `lower-event-to-daw`
    folds it into its track.
    """

    name = "daw.rack"
    track = prop_def(StringAttr)
    volume = opt_prop_def(FloatAttr)
    pan = opt_prop_def(FloatAttr)
    color = opt_prop_def(StringAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = (
        "$track (`volume` $volume^)? (`pan` $pan^)? (`color` $color^)? attr-dict-with-keyword $body"
    )

    def __init__(
        self,
        track: str,
        ops: Sequence,
        volume: float | None = None,
        pan: float | None = None,
        color: str | None = None,
    ):
        props: dict[str, Attribute] = {"track": StringAttr(track)}
        if volume is not None:
            props["volume"] = float_attr(volume)
        if pan is not None:
            props["pan"] = float_attr(pan)
        if color is not None:
            props["color"] = StringAttr(color)
        super().__init__(properties=props, regions=[Region(Block(ops))])


@irdl_op_definition
class PluginOp(IRDLOperation):
    """
    A device on a track, in chain order.

    `device` is the local name automation refers to. `params` maps a parameter's
    published name to a normalised value. `patch` names a preset the plugin starts
    from, such as Surge XT's "Keys/Artificial 1"; `params` are then written on top.
    The name stays in the IR and becomes plugin state only when it is sent.
    """

    name = "daw.plugin"
    device = prop_def(StringAttr)
    identifier = prop_def(StringAttr)
    params = prop_def(DictionaryAttr)
    patch = opt_prop_def(StringAttr)
    assembly_format = "$device `is` $identifier (`patch` $patch^)? `with` $params attr-dict"

    def __init__(
        self, device: str, identifier: str, params: dict[str, object], patch: str | None = None
    ):
        props: dict[str, Attribute] = {
            "device": StringAttr(device),
            "identifier": StringAttr(identifier),
            "params": to_attr(params),
        }
        if patch is not None:
            props["patch"] = StringAttr(patch)
        super().__init__(properties=props)


@irdl_op_definition
class ClipOp(IRDLOperation):
    """A MIDI clip. `key` names it across recompiles, such as "verse#1/bass"."""

    name = "daw.clip"
    key = prop_def(StringAttr)
    start = prop_def(IntegerAttr)
    length = prop_def(IntegerAttr)
    body = region_def("single_block")
    traits = traits_def(NoTerminator())
    assembly_format = "$key `at` $start `for` $length attr-dict-with-keyword $body"

    def __init__(self, key: str, start: int, length: int, ops: Sequence):
        super().__init__(
            properties={
                "key": StringAttr(key),
                "start": IntegerAttr(start, i64),
                "length": IntegerAttr(length, i64),
            },
            regions=[Region(Block(ops))],
        )

    def notes(self) -> list[NoteOp]:
        return [op for op in self.body.block.ops if isinstance(op, NoteOp)]

    def controllers(self) -> list[ControllerOp]:
        return [op for op in self.body.block.ops if isinstance(op, ControllerOp)]


@irdl_op_definition
class NoteOp(IRDLOperation):
    """A note in ticks from the start of its clip: `daw.note 60 at 480 for 240 vel 100`."""

    name = "daw.note"
    pitch = prop_def(IntegerAttr)
    start = prop_def(IntegerAttr)
    dur = prop_def(IntegerAttr)
    vel = prop_def(IntegerAttr)

    def __init__(self, pitch: int, start: int, dur: int, vel: int):
        super().__init__(
            properties={
                "pitch": IntegerAttr(pitch, i64),
                "start": IntegerAttr(start, i64),
                "dur": IntegerAttr(dur, i64),
                "vel": IntegerAttr(vel, i64),
            }
        )

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (
            self.pitch.value.data,
            self.start.value.data,
            self.dur.value.data,
            self.vel.value.data,
        )

    def print(self, printer: Printer) -> None:
        pitch, start, dur, vel = self.as_tuple()
        printer.print_string(f" {pitch} at {start} for {dur} vel {vel}")

    @classmethod
    def parse(cls, parser: Parser) -> NoteOp:
        pitch = parser.parse_integer(allow_boolean=False, allow_negative=False)
        parser.parse_keyword("at")
        start = parser.parse_integer(allow_boolean=False, allow_negative=False)
        parser.parse_keyword("for")
        dur = parser.parse_integer(allow_boolean=False, allow_negative=False)
        parser.parse_keyword("vel")
        vel = parser.parse_integer(allow_boolean=False, allow_negative=False)
        return cls(pitch, start, dur, vel)


@irdl_op_definition
class AutomationOp(IRDLOperation):
    """A parameter's curve. `points` alternates tick and normalised value."""

    name = "daw.automation"
    device = prop_def(StringAttr)
    param = prop_def(StringAttr)
    points = prop_def(ArrayAttr)
    assembly_format = "$device `param` $param $points attr-dict"

    def __init__(self, device: str, param: str, points: Sequence[tuple[int, float]]):
        flat: list[object] = []
        for at, value in points:
            flat.extend((int(at), float(value)))
        super().__init__(
            properties={
                "device": StringAttr(device),
                "param": StringAttr(param),
                "points": ArrayAttr([_point_attr(v) for v in flat]),
            }
        )

    def point_list(self) -> list[tuple[int, float]]:
        values = [_point_value(a) for a in self.points.data]
        return [(int(t), float(v)) for t, v in zip(values[0::2], values[1::2], strict=True)]


@irdl_op_definition
class ControllerOp(IRDLOperation):
    """
    A MIDI controller lane in a clip: `pitchbend`, `pressure` or `cc0` to `cc127`.

    `points` alternates tick, from the start of the clip, and a value from 0 to 1.
    Pitch bend rests at 0.5. A controller holds its value until the next point, so a
    smooth bend is many points.
    """

    name = "daw.controller"
    controller = prop_def(StringAttr)
    points = prop_def(ArrayAttr)
    assembly_format = "$controller $points attr-dict"

    def __init__(self, controller: str, points: Sequence[tuple[int, float]]):
        flat: list[object] = []
        for at, value in points:
            flat.extend((int(at), float(value)))
        super().__init__(
            properties={
                "controller": StringAttr(controller),
                "points": ArrayAttr([_point_attr(v) for v in flat]),
            }
        )

    def point_list(self) -> list[tuple[int, float]]:
        values = [_point_value(a) for a in self.points.data]
        return [(int(t), float(v)) for t, v in zip(values[0::2], values[1::2], strict=True)]


def _point_attr(value: object) -> Attribute:
    return float_attr(value) if isinstance(value, float) else to_attr(value)


def _point_value(attr: Attribute) -> float | int:
    return attr.value.data


@irdl_op_definition
class SendOp(IRDLOperation):
    """A send from this track to another, at a linear gain."""

    name = "daw.send"
    destination = prop_def(StringAttr)
    gain = prop_def(FloatAttr)
    assembly_format = "`to` $destination `gain` $gain attr-dict"

    def __init__(self, destination: str, gain: float):
        super().__init__(
            properties={"destination": StringAttr(destination), "gain": float_attr(gain)}
        )


DawDialect = Dialect(
    "daw",
    [
        ProjectOp,
        TempoOp,
        MeterOp,
        MarkerOp,
        TrackOp,
        PluginOp,
        ClipOp,
        NoteOp,
        ControllerOp,
        AutomationOp,
        SendOp,
    ],
    [],
)
