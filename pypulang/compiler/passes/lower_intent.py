"""
`lower-intent-to-score`: lay the form out in time and make the slots.

Patterns are not expanded here. Each chord of each part becomes a `score.slot`
holding a close-position voicing, so later passes can revoice it before any note
exists. Literal notes have nothing left to decide and go straight into bars, and so
do melodies, once their motifs are resolved in the section's key and fitted to its
chords.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass

from pypulang.compiler.dialects import daw, event, intent, score
from pypulang.compiler.dialects.mus import from_attr
from pypulang.compiler.locs import in_section, loc_key
from pypulang.compiler.notes import NoteRecord, add_notes
from pypulang.compiler.timeline import Timeline
from pypulang.context_patterns import CONTEXT_PATTERNS
from pypulang.ir.intent import Chord, Key, TimeSignature
from pypulang.motifs import realize
from pypulang.resolution import resolve_chord


@dataclass
class _Occurrence:
    op: intent.SectionOp
    marker: score.SectionOp


def _layout(piece: intent.PieceOp) -> list[_Occurrence]:
    by_name = {s.section.data: s for s in piece.sections()}
    order = [s.data for s in piece.form.data] if piece.form is not None else list(by_name.keys())
    counts: dict[str, int] = {}
    time = Fraction(0)
    bar = 1
    result = []
    for name in order:
        if name not in by_name:
            raise ValueError(f"Unknown section in form: {name}")
        op = by_name[name]
        counts[name] = counts.get(name, 0) + 1
        key = op.key.data if op.key is not None else piece.key.data
        meter = op.meter.data if op.meter is not None else piece.meter.data
        bars = op.bars.value.data
        marker = score.SectionOp(name, counts[name], bar, bars, time, key, meter)
        marker.location = in_section(name, name, counts[name])
        result.append(_Occurrence(op, marker))
        time += bars * meter.beats_per_bar
        bar += bars
    return result


def _chord_spans(
    harmony: intent.HarmonyOp, section_beats: Fraction, meter: TimeSignature
) -> list[tuple[Chord, Fraction, Fraction]]:
    """(chord, start, duration) in beats from the section's start, stretched to fill it."""
    changes = harmony.changes()
    if not changes:
        return []
    bars = harmony.unit.data == "bars"
    total = sum((d for _, d in changes), Fraction(0))
    total_beats = total * meter.beats_per_bar if bars else total
    scale = section_beats / total_beats if total_beats > 0 and section_beats > 0 else Fraction(1)
    spans = []
    at = Fraction(0)
    for chord, duration in changes:
        beats = (duration * meter.beats_per_bar if bars else duration) * scale
        spans.append((chord, at, beats))
        at += beats
    return spans


def _first_chord(op: intent.SectionOp) -> Chord | None:
    harmony = op.harmony()
    changes = harmony.changes() if harmony is not None else []
    return changes[0][0] if changes else None


def _slots_for(
    occurrence: _Occurrence,
    following: Chord | None,
    track: intent.TrackOp,
    pattern: intent.PatternOp,
) -> list[score.SlotOp]:
    marker = occurrence.marker
    key: Key = marker.key.data
    meter: TimeSignature = marker.meter.data
    harmony = pattern.harmony.owner
    assert isinstance(harmony, intent.HarmonyOp)
    spans = _chord_spans(harmony, marker.length, meter)
    if not spans and pattern.kind.data in CONTEXT_PATTERNS:
        # Drums need no chords. A section with no harmony still has to play them.
        spans = [(Chord("I"), Fraction(0), marker.length)]
    slots = []
    for index, (chord, at, beats) in enumerate(spans):
        next_chord = spans[index + 1][0] if index + 1 < len(spans) else following
        slot = score.SlotOp(
            kind=pattern.kind.data,
            chord=chord,
            key=key,
            meter=meter,
            start=marker.start.data + at,
            dur=beats,
            pitches=resolve_chord(chord, key, octave=4),
            params=from_attr(pattern.params),
            section=marker.tag,
            octave=track.octave.value.data,
            velocity=track.velocity.value.data,
            voicing=track.voicing.data if track.voicing is not None else None,
            next_chord=next_chord,
        )
        slot.location = in_section(
            f"{marker.section.data}/{track.track.data}/c{index}",
            marker.section.data,
            marker.occurrence.value.data,
        )
        slots.append(slot)
    return slots


def _literal_records(
    occurrence: _Occurrence, track: intent.TrackOp, notes: intent.NotesOp
) -> list[NoteRecord]:
    start = occurrence.marker.start.data
    octave = track.octave.value.data
    default_velocity = track.velocity.value.data
    records = []
    for op in notes.body.block.ops:
        assert isinstance(op, intent.NoteOp)
        velocity = op.vel.value.data if op.vel is not None else default_velocity
        records.append(
            NoteRecord(
                pitch=op.pitch.value.data + octave * 12,
                start=start + op.offset.data,
                dur=op.dur.data,
                vel=velocity,
                articulation=op.art.data if op.art is not None else None,
            )
        )
    return records


def _melody_records(
    occurrence: _Occurrence,
    track: intent.TrackOp,
    melody: intent.MelodyOp,
    motifs: dict[str, str],
) -> list[NoteRecord]:
    marker = occurrence.marker
    meter: TimeSignature = marker.meter.data
    harmony = melody.harmony.owner
    assert isinstance(harmony, intent.HarmonyOp)
    try:
        notes = realize(
            melody.phrase.data,
            motifs,
            marker.key.data,
            _chord_spans(harmony, marker.length, meter),
            meter.beats_per_bar,
            low=melody.low.value.data,
            high=melody.high.value.data,
            fit=bool(melody.fit.value.data),
            # The same in every occurrence, as written notes are
            seed=f"{marker.section.data}/{track.track.data}",
        )
    except ValueError as error:
        raise ValueError(f"{marker.section.data}/{track.track.data}: {error}") from error
    start = marker.start.data
    octave = track.octave.value.data
    base = track.velocity.value.data
    records = []
    for note in notes:
        if note.start >= marker.length:
            break  # a phrase longer than its section stops at the section's end
        records.append(
            NoteRecord(
                pitch=note.pitch + octave * 12,
                start=start + note.start,
                dur=min(note.dur, marker.length - note.start),
                vel=max(1, min(127, int(base * note.velocity_scale))),
                articulation=note.articulation,
            )
        )
    return records


def _chord_timeline(occurrences: list[_Occurrence]) -> list[score.ChordOp]:
    timeline = []
    for occurrence in occurrences:
        harmony = occurrence.op.harmony()
        if harmony is None:
            continue
        marker = occurrence.marker
        for chord, at, beats in _chord_spans(harmony, marker.length, marker.meter.data):
            timeline.append(score.ChordOp(chord, marker.key.data, marker.start.data + at, beats))
    return timeline


@dataclass(frozen=True)
class LowerIntentToScore(ModulePass):
    name = "lower-intent-to-score"

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        pieces = [o for o in op.body.block.ops if isinstance(o, intent.PieceOp)]
        if len(pieces) != 1:
            raise ValueError(f"Expected one intent.piece, found {len(pieces)}")
        piece = pieces[0]
        occurrences = _layout(piece)
        timeline = Timeline([o.marker for o in occurrences])
        motifs = piece.motifs()

        parts: dict[str, score.PartOp] = {}
        for index, occurrence in enumerate(occurrences):
            following = (
                _first_chord(occurrences[index + 1].op) if index + 1 < len(occurrences) else None
            )
            for track in occurrence.op.tracks():
                if track.muted.value.data:
                    continue
                name = track.track.data
                if name not in parts:
                    parts[name] = score.PartOp(name, track.role.data, track.instrument.data, [])
                    parts[name].location = in_section(
                        f"{occurrence.marker.section.data}/{name}",
                        occurrence.marker.section.data,
                        occurrence.marker.occurrence.value.data,
                    )
                for content in track.body.block.ops:
                    if isinstance(content, intent.PatternOp):
                        for slot in _slots_for(occurrence, following, track, content):
                            parts[name].body.block.add_op(slot)
                    elif isinstance(content, intent.NotesOp):
                        add_notes(
                            parts[name],
                            timeline,
                            _literal_records(occurrence, track, content),
                        )
                    elif isinstance(content, intent.MelodyOp):
                        add_notes(
                            parts[name],
                            timeline,
                            _melody_records(occurrence, track, content, motifs),
                        )
            for curve in occurrence.op.curves():
                name = curve.track.data
                if name not in parts:
                    # Automation on a track with no notes, such as a bus.
                    parts[name] = score.PartOp(name, "harmony", "", [])
                start = occurrence.marker.start.data
                lowered = event.CurveOp(
                    curve.target.data, [(start + t, v) for t, v in curve.point_list()]
                )
                lowered.location = curve.location
                parts[name].body.block.add_op(lowered)
            # Audio rides with the part like a curve does, one per occurrence,
            # located at its occurrence so each is its own clip in the DAW.
            for placed in occurrence.op.audio():
                name = placed.track.data
                if name not in parts:
                    parts[name] = score.PartOp(name, "harmony", "", [])
                lowered = event.AudioOp(
                    placed.file.data,
                    occurrence.marker.start.data + placed.at.data,
                    placed.length.data if placed.length is not None else None,
                    placed.offset.value.data,
                    placed.gain.value.data,
                )
                lowered.location = in_section(
                    loc_key(placed.location),
                    occurrence.marker.section.data,
                    occurrence.marker.occurrence.value.data,
                )
                parts[name].body.block.add_op(lowered)

        racks = [o for o in piece.body.block.ops if isinstance(o, daw.RackOp)]
        for rack in racks:
            piece.body.block.detach_op(rack)

        title = piece.title.data
        result = score.ScoreOp(
            title,
            piece.tempo.value.data,
            piece.key.data,
            piece.meter.data,
            [
                *racks,
                *[o.marker for o in occurrences],
                *_chord_timeline(occurrences),
                *parts.values(),
            ],
        )
        result.location = piece.location
        op.body.block.detach_op(piece)
        op.body.block.add_op(result)
