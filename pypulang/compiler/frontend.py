"""Import a `Piece` into the `intent` dialect."""

from __future__ import annotations

from xdsl.dialects.builtin import ModuleOp

from pypulang.compiler.dialects import intent
from pypulang.compiler.locs import name_loc
from pypulang.ir.intent import Notes, Pattern, Piece, Section, Track


def _track_op(section: Section, track: Track, harmony: intent.HarmonyOp | None) -> intent.TrackOp:
    body: list = []
    content = track.content
    if isinstance(content, Pattern):
        if harmony is None:
            # A pattern needs a harmony operand, and an empty progression makes no notes.
            raise AssertionError("import_piece always makes a harmony op for patterns")
        op = intent.PatternOp(content.pattern_type, harmony.result, dict(content.params))
        op.location = name_loc(f"{section.name}/{track.name}/pattern")
        body.append(op)
    elif isinstance(content, Notes):
        notes = [
            intent.NoteOp(n.pitch, n.offset, n.duration, n.velocity)
            for n in content.notes
            if n.pitch >= 0
        ]
        op = intent.NotesOp(notes)
        op.location = name_loc(f"{section.name}/{track.name}/notes")
        body.append(op)
    result = intent.TrackOp(
        track=track.name,
        role=track.role,
        instrument=str(track.instrument),
        octave=track.octave_shift,
        velocity=track.velocity,
        muted=track.muted,
        voicing=track.voicing,
        ops=body,
    )
    result.location = name_loc(f"{section.name}/{track.name}")
    return result


def _section_op(section: Section) -> intent.SectionOp:
    harmony = intent.HarmonyOp(
        [c.chord for c in section.harmony.changes],
        [c.duration for c in section.harmony.changes],
        section.harmony.duration_unit,
    )
    harmony.location = name_loc(f"{section.name}/harmony")
    tracks = [_track_op(section, t, harmony) for t in section.tracks]
    op = intent.SectionOp(
        section.name, section.bars, section.key, section.time_signature, [harmony, *tracks]
    )
    op.location = name_loc(section.name)
    return op


def import_piece(piece: Piece) -> ModuleOp:
    """Build an `intent` module from a `Piece`."""
    op = intent.PieceOp(
        title=piece.title or "",
        tempo=piece.tempo,
        key=piece.key,
        meter=piece.time_signature,
        form=piece.form,
        ops=[_section_op(s) for s in piece.sections],
    )
    op.location = name_loc("piece")
    return ModuleOp([op])
