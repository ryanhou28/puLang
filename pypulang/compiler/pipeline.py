"""Running the compiler."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from io import StringIO

from xdsl.context import Context
from xdsl.dialects.builtin import Builtin, ModuleOp
from xdsl.parser import Parser
from xdsl.passes import ModulePass
from xdsl.printer import Printer

from pypulang.compiler.dialects.daw import DawDialect
from pypulang.compiler.dialects.event import EventDialect
from pypulang.compiler.dialects.intent import IntentDialect
from pypulang.compiler.dialects.mus import Mus
from pypulang.compiler.dialects.score import ScoreDialect
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

    @property
    def daw(self) -> ModuleOp:
        return self.stages["daw"]

    @property
    def warnings(self) -> list[str]:
        last = next(reversed(self.stages.values()))
        return warnings_of(last)


def compile_piece(
    piece: Piece | ModuleOp,
    until: str = "daw",
    intent_passes: Sequence[ModulePass] = (),
    score_passes: Sequence[ModulePass] = (),
    event_passes: Sequence[ModulePass] = (),
    daw_passes: Sequence[ModulePass] = (),
    keep_trace: bool = False,
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

    plan: list[tuple[str, list[ModulePass]]] = [
        ("intent", list(intent_passes)),
        (
            "score",
            [LowerIntentToScore(), VoiceLead(), *score_passes, RealizePatterns()],
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
