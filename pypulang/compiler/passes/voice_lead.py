"""
`voice-lead`: choose the pitches of every slot that asks for a voicing.

Slots with no voicing keep their close-position pitches. Slots that do ask are
grouped by run: consecutive chords in one part form one problem, and a gap in the
part starts a new one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass

from pypulang.compiler.dialects import score
from pypulang.compiler.locs import loc_key
from pypulang.harmony import chord_symbol
from pypulang.voicing import DEFAULT_REGISTER, Register, candidates_for, lead_voices

_SPEC_RE = re.compile(r"^(\w+)(?:\((\d+),(\d+)\))?$")


def parse_spec(spec: str) -> tuple[str, Register]:
    """Read a voicing spec: a strategy name, optionally with `(low,high)` MIDI bounds."""
    m = _SPEC_RE.match(spec)
    if m is None:
        raise ValueError(f"Cannot read voicing {spec!r}")
    if m.group(2) is None:
        return m.group(1), DEFAULT_REGISTER
    return m.group(1), Register(int(m.group(2)), int(m.group(3)))


def _runs(slots: list[score.SlotOp]) -> list[list[score.SlotOp]]:
    runs: list[list[score.SlotOp]] = []
    for slot in slots:
        if slot.voicing is None:
            continue
        if (
            runs
            and runs[-1][-1].voicing == slot.voicing
            and runs[-1][-1].start.data + runs[-1][-1].dur.data == slot.start.data
        ):
            runs[-1].append(slot)
        else:
            runs.append([slot])
    return runs


def voice_part(part: score.PartOp) -> None:
    for run in _runs(part.slots()):
        name, register = parse_spec(run[0].voicing.data)
        options = [candidates_for(name, slot.chord.data, slot.key.data, register) for slot in run]
        for slot, candidates in zip(run, options, strict=True):
            if not candidates:
                raise ValueError(
                    f"{loc_key(slot.location)}: no {name} voicing of "
                    f"{chord_symbol(slot.chord.data, slot.key.data)} fits MIDI "
                    f"{register.low}-{register.high}; widen the range, or voice it another way"
                )
        for slot, voicing in zip(run, lead_voices(options, register), strict=True):
            slot.set_pitches(voicing)


@dataclass(frozen=True)
class VoiceLead(ModulePass):
    name = "voice-lead"

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        for top in op.body.block.ops:
            if isinstance(top, score.ScoreOp):
                for part in top.parts():
                    voice_part(part)
