"""`lower-score-to-event`: from named notes in bars to timed events."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass

from pypulang.compiler.dialects import daw, event, score
from pypulang.compiler.spelling import midi_of

_ARTICULATION_LENGTH = {
    "staccato": Fraction(1, 2),
    "staccatissimo": Fraction(1, 4),
    "portato": Fraction(3, 4),
}
_ARTICULATION_ACCENT = {"accent": Fraction(6, 5), "marcato": Fraction(5, 4)}


def _performed(note: score.NoteOp) -> tuple[Fraction, int]:
    dur = note.dur.data
    vel = note.vel.value.data
    if note.articulation is not None:
        name = note.articulation.data
        dur = dur * _ARTICULATION_LENGTH.get(name, Fraction(1))
        vel = min(127, int(vel * _ARTICULATION_ACCENT.get(name, Fraction(1))))
    return dur, vel


@dataclass(frozen=True)
class LowerScoreToEvent(ModulePass):
    name = "lower-score-to-event"

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        scores = [o for o in op.body.block.ops if isinstance(o, score.ScoreOp)]
        if len(scores) != 1:
            raise ValueError(f"Expected one score.score, found {len(scores)}")
        top = scores[0]
        tempos = top.tempos() or [score.TempoOp(Fraction(0), top.tempo.value.data)]
        ops: list = [event.TempoOp(t.at.data, t.bpm.value.data) for t in tempos]
        for section in top.sections():
            marker = event.SectionOp(
                section.tag, section.start.data, section.length, section.meter.data
            )
            marker.location = section.location
            ops.append(marker)
        for rack in [o for o in top.body.block.ops if isinstance(o, daw.RackOp)]:
            top.body.block.detach_op(rack)
            ops.append(rack)
        for part in top.parts():
            notes = []
            for bar in part.bars():
                for note in bar.notes():
                    dur, vel = _performed(note)
                    lowered = event.NoteOp(
                        midi_of(note.pitch.data), bar.start.data + note.beat.data, dur, vel
                    )
                    lowered.location = note.location
                    notes.append(lowered)
            notes.sort(key=lambda n: (n.start.data, n.pitch.value.data))
            curves = [o for o in part.body.block.ops if isinstance(o, event.CurveOp)]
            audio = [o for o in part.body.block.ops if isinstance(o, event.AudioOp)]
            for carried in [*curves, *audio]:
                part.body.block.detach_op(carried)
            track = event.TrackOp(
                part.part.data, part.role.data, part.instrument.data, [*notes, *curves, *audio]
            )
            track.location = part.location
            ops.append(track)
        result = event.StreamOp(top.title.data, ops)
        result.location = top.location
        op.body.block.detach_op(top)
        op.body.block.add_op(result)
