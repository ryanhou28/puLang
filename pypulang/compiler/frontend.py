"""Import a `Piece` into the `intent` dialect."""

from __future__ import annotations

from xdsl.dialects.builtin import ModuleOp

from pypulang.compiler.dialects import daw, intent
from pypulang.compiler.locs import name_loc
from pypulang.ir.intent import Notes, Pattern, Piece, Rack, Section, Track


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
            intent.NoteOp(n.pitch, n.offset, n.duration, n.velocity, n.articulation)
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
    curves = []
    for curve in section.curves:
        curve_op = intent.CurveOp(curve.track, curve.target, curve.points)
        curve_op.location = name_loc(f"{section.name}/{curve.track}/{curve.target}")
        curves.append(curve_op)
    op = intent.SectionOp(
        section.name, section.bars, section.key, section.time_signature, [harmony, *tracks, *curves]
    )
    op.location = name_loc(section.name)
    return op


def _rack_op(rack: Rack) -> daw.RackOp:
    ops: list = [daw.PluginOp(d.name, d.identifier, dict(d.params), d.patch) for d in rack.devices]
    ops.extend(daw.SendOp(destination, gain) for destination, gain in rack.sends.items())
    op = daw.RackOp(rack.track, ops, rack.volume, rack.pan, rack.color)
    op.location = name_loc(f"rack/{rack.track}")
    return op


def import_piece(piece: Piece) -> ModuleOp:
    """Build an `intent` module from a `Piece`."""
    op = intent.PieceOp(
        title=piece.title or "",
        tempo=piece.tempo,
        key=piece.key,
        meter=piece.time_signature,
        form=piece.form,
        ops=[*[_rack_op(r) for r in piece.racks], *[_section_op(s) for s in piece.sections]],
    )
    op.location = name_loc("piece")
    return ModuleOp([op])
