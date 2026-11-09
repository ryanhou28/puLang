"""Running the compiler."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from io import StringIO

from xdsl.context import Context
from xdsl.dialects.builtin import Builtin, ModuleOp
from xdsl.parser import Parser
from xdsl.passes import ModulePass
from xdsl.printer import Printer

from pypulang.compiler.dialects import event
from pypulang.compiler.dialects.daw import DawDialect
from pypulang.compiler.dialects.event import EventDialect
from pypulang.compiler.dialects.intent import IntentDialect
from pypulang.compiler.dialects.mus import Mus
from pypulang.compiler.dialects.score import ScoreDialect
from pypulang.compiler.edits import ApplyIntentEdits, ApplyScoreEdits, Edit, EditReport
from pypulang.compiler.frontend import import_piece
from pypulang.compiler.passes.lower_event import LowerEventToDaw, warnings_of
from pypulang.compiler.passes.lower_intent import LowerIntentToScore
from pypulang.compiler.passes.lower_score import LowerScoreToEvent
from pypulang.compiler.passes.realize import RealizePatterns
from pypulang.compiler.passes.voice_lead import VoiceLead
from pypulang.ir.intent import Piece

STAGES = ("intent", "score", "event", "daw")


def make_context() -> Context:
    """A context with every puLang dialect loaded."""
    ctx = Context()
    for dialect in (Builtin, Mus, IntentDialect, ScoreDialect, EventDialect, DawDialect):
        ctx.load_dialect(dialect)
    return ctx


def print_ir(module: ModuleOp, locations: bool = False) -> str:
    """The text form of a module. With `locations`, it parses back losslessly."""
    stream = StringIO()
    Printer(stream=stream, print_debuginfo=locations).print_op(module)
    return stream.getvalue() + "\n"


def parse_ir(text: str) -> ModuleOp:
    """Read a module printed by `print_ir`, or written by hand."""
    module = Parser(make_context(), text).parse_module()
    module.verify()
    return module


@dataclass
class CompileResult:
    """What a compile produced: the module at each stage, and any warnings."""

    stages: dict[str, ModuleOp] = field(default_factory=dict)
    trace: list[tuple[str, ModuleOp]] = field(default_factory=list)
    edits: EditReport = field(default_factory=EditReport)

    @property
    def daw(self) -> ModuleOp:
        return self.stages["daw"]

    @property
    def warnings(self) -> list[str]:
        last = next(reversed(self.stages.values()))
        return [*warnings_of(last), *self.edits.lines()]


def compile_piece(
    piece: Piece | ModuleOp,
    until: str = "daw",
    intent_passes: Sequence[ModulePass] = (),
    score_passes: Sequence[ModulePass] = (),
    event_passes: Sequence[ModulePass] = (),
    daw_passes: Sequence[ModulePass] = (),
    keep_trace: bool = False,
    edits: Sequence[Edit] = (),
) -> CompileResult:
    """
    Compile a piece down to `until`.

    Args:
        piece: A `Piece`, or an `intent` module to start from
        until: The last stage to run: "intent", "score", "event", or "daw"
        intent_passes: Run on the intent module before lowering
        score_passes: Run on slots, before patterns are expanded
        event_passes: Run on the event stream
        daw_passes: Run on the finished project
        keep_trace: Keep a copy of the module after every single pass
        edits: Edits made above the notes, applied where they were made: intent
            edits after `intent_passes`, score chords before voice leading, exact
            voicings after it

    Returns:
        A CompileResult holding a copy of the module at each stage reached
    """
    if until not in STAGES:
        raise ValueError(f"Unknown stage {until!r}. Stages: {STAGES}")

    ctx = make_context()
    module = piece if isinstance(piece, ModuleOp) else import_piece(piece)
    module.verify()
    result = CompileResult()

    def run(passes: Sequence[ModulePass]) -> None:
        for one in passes:
            one.apply(ctx, module)
            module.verify()
            if keep_trace:
                result.trace.append((one.name, module.clone()))

    edits = tuple(edits)
    # The edit passes run only when there are edits, so a song without any traces
    # exactly as it did before edits existed.
    intent_edits = [ApplyIntentEdits(edits, result.edits)] if edits else []
    score_chords = [ApplyScoreEdits(edits, ("chord",), result.edits)] if edits else []
    score_pitches = [ApplyScoreEdits(edits, ("pitches",), result.edits)] if edits else []
    plan: list[tuple[str, list[ModulePass]]] = [
        ("intent", [*intent_passes, *intent_edits]),
        (
            "score",
            [
                LowerIntentToScore(),
                *score_chords,
                VoiceLead(),
                *score_pitches,
                *score_passes,
                RealizePatterns(),
            ],
        ),
        ("event", [LowerScoreToEvent(), *event_passes]),
        ("daw", [LowerEventToDaw(), *daw_passes]),
    ]
    for stage, passes in plan:
        run(passes)
        result.stages[stage] = module.clone()
        if stage == until:
            break
    return result


def playback_events(
    piece: Piece, from_bar: int | None = None, section: str | None = None
) -> tuple[list[tuple[int, float, float, int, str, str]], float]:
    """
    A compiled piece as flat events, in the shape the playback backends take.

    Args:
        piece: The piece
        from_bar: Start here, counting bars from 1
        section: Play only this section

    Returns:
        (pitch, start, duration, velocity, track, role) tuples, and the tempo
    """
    if section is not None:
        if section not in [s.name for s in piece.sections]:
            raise ValueError(f"Unknown section: {section}")
        piece = replace(piece, form=[section])

    module = compile_piece(piece, until="event").stages["event"]
    stream = next(o for o in module.body.block.ops if isinstance(o, event.StreamOp))

    skip = Fraction(0)
    if from_bar is not None and from_bar > 1:
        bars_left = from_bar - 1
        for marker in stream.sections():
            beats_per_bar = marker.meter.data.beats_per_bar
            bars = int(marker.length.data / beats_per_bar)
            taken = min(bars, bars_left)
            skip += taken * beats_per_bar
            bars_left -= taken

    events = [
        (
            n.pitch.value.data,
            float(n.start.data - skip),
            float(n.dur.data),
            n.vel.value.data,
            t.track.data,
            t.role.data,
        )
        for t in stream.tracks()
        for n in t.notes()
        if n.start.data >= skip
    ]
    return events, stream.tempos()[0].bpm.value.data
