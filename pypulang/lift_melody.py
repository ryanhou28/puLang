"""
Reading hand edits to a melody as edits of its motifs or its phrase.

A melody written as motifs is lowered note by note, so a note dragged in the
piano roll is first a note edit. It may mean more: the motif itself should go
there, wherever it is used, or this statement of it should sit a step higher, or
end on another degree. This proposes those readings; `pypulang.lift` checks each
by lowering the song with it, as it does chords and voicings.

Each sounding note is traced back to its placement in the phrase and to the note
of the motif as written that it came from, through every development. A pitch
change is read in scale steps against the note as written, before it was fitted
to the chord, and undone through inversions; a move or a new length is undone
through stretching. Notes an ornament added belong to no motif note and are left
to the note edits.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import TYPE_CHECKING, Any

from pypulang.compiler.dialects import intent
from pypulang.compiler.dialects.mus import format_rational
from pypulang.compiler.edits import Edit
from pypulang.compiler.passes.lower_event import PPQ
from pypulang.compiler.passes.lower_intent import realize_melody
from pypulang.ir.intent import Key
from pypulang.motifs import (
    MelodyNote,
    Placement,
    Trace,
    degree_of,
    format_motif,
    format_phrase,
    parse_motif,
    parse_phrase,
)

if TYPE_CHECKING:
    from pypulang.inspector import Model
    from pypulang.lift import Suggestion


@dataclass
class _Edited:
    loc: str
    trace: Trace
    note: MelodyNote
    entry: dict[str, Any]
    step: int = 0  # scale steps the pitch moved from the note as written
    accidental: int = 0  # of the new pitch in the key
    moved: Fraction = Fraction(0)  # beats
    stretched: Fraction = Fraction(0)  # beats


def _quantize(beats: Fraction) -> Fraction:
    """To the nearest sixteenth or eighth-note triplet, whichever is closer."""
    sixteenth = Fraction(round(beats * 4), 4)
    triplet = Fraction(round(beats * 3), 3)
    return sixteenth if abs(sixteenth - beats) <= abs(triplet - beats) else triplet


def _locations(
    traced: list[tuple[MelodyNote, Trace]],
    tag: str,
    track: str,
    bar_beats: Fraction,
    length: Fraction,
) -> dict[str, tuple[MelodyNote, Trace]]:
    """Each note's location, as `add_notes` names it: bar+beat, voices numbered from the bottom."""
    onsets: dict[Fraction, list[tuple[MelodyNote, Trace]]] = defaultdict(list)
    for note, trace in traced:
        if note.start < length:
            onsets[note.start].append((note, trace))
    found = {}
    for start, items in onsets.items():
        bar = int(start // bar_beats)
        beat = start - bar * bar_beats
        for voice, item in enumerate(sorted(items, key=lambda i: i[0].pitch)):
            found[f"{tag}/{track}/{bar + 1}+{format_rational(beat)}/v{voice}"] = item
    return found


def _ops(placement: Placement) -> tuple[int, Fraction, bool, bool]:
    """How a placement's developments act on a motif note: (sign, stretch, reversed, end)."""
    names = [op for op, _ in placement.ops]
    stretch = Fraction(1)
    for op, arg in placement.ops:
        if op == "x":
            stretch *= Fraction(arg)
    return (-1 if names.count("inv") % 2 else 1), stretch, "rev" in names, "end" in names


def _motif_reading(
    name: str, text: str, placement: Placement, edited: list[_Edited], last: Trace | None
) -> str | None:
    """The motif as written that would give these edits in this placement, or None."""
    sign, stretch, reversed_, has_end = _ops(placement)
    motif = parse_motif(text)
    notes = {n.origin: n for n in motif.notes}
    changed = False
    for one in edited:
        origin = one.trace.note.origin
        if origin is None or origin not in notes:
            continue
        if has_end and last is not None and one.trace is last:
            continue  # its pitch is the "end" development's, not the motif's
        if one.entry.get("deleted"):
            del notes[origin]
            changed = True
            continue
        base = notes[origin]
        updated = replace(base, step=base.step + sign * one.step, accidental=sign * one.accidental)
        if (one.moved or one.stretched) and not reversed_:
            updated = replace(
                updated,
                start=updated.start + one.moved / stretch,
                dur=updated.dur + one.stretched / stretch,
            )
        if updated.dur <= 0 or updated.start < 0:
            return None
        if updated != base:
            notes[origin] = updated
            changed = True
    if not changed or not notes:
        return None
    kept = sorted(notes.values(), key=lambda n: n.start)
    length = max(motif.length, max(n.start + n.dur for n in kept))
    written = format_motif(kept, length)
    return written if written != text else None


def _phrase_readings(
    phrase: str, index: int, all_of_it: list[Trace], edited: list[_Edited], key: Key
) -> list[tuple[str, str]]:
    """New phrase texts that put this placement where the edits put it, with a reason."""
    placements = parse_phrase(phrase)
    placement = placements[index]
    found = []
    pitch_only = all(not e.entry.get("deleted") and not e.moved and not e.stretched for e in edited)
    if not pitch_only:
        return found
    shifts = {e.step for e in edited}
    if len(edited) == len(all_of_it) and len(shifts) == 1 and next(iter(shifts)):
        shift = next(iter(shifts))
        ops = list(placement.ops)
        octaves, rest = divmod(abs(shift), 7)
        if rest == 0:
            ops.extend([("^" if shift > 0 else "v", None)] * octaves)
            what = f"{octaves} octave(s) {'up' if shift > 0 else 'down'}"
        else:
            if ops and ops[-1][0] in ("+", "-"):
                previous = int(ops.pop()[1]) * (1 if placement.ops[-1][0] == "+" else -1)
                shift += previous
            if shift:
                ops.append(("+" if shift > 0 else "-", str(abs(shift))))
            what = f"{abs(next(iter(shifts)))} step(s) {'up' if next(iter(shifts)) > 0 else 'down'}"
        placements[index] = replace(placement, ops=tuple(ops))
        found.append((format_phrase(placements), what))
    elif len(edited) == 1 and edited[0].trace is all_of_it[-1] and edited[0].accidental == 0:
        one = edited[0]
        new_pitch = one.entry["note"][0]
        degree = degree_of(new_pitch, key)[0] % 7 + 1
        ops = [op for op in placement.ops if op[0] != "end"] + [("end", str(degree))]
        placements = list(placements)
        placements[index] = replace(placement, ops=tuple(ops))
        found.append((format_phrase(placements), f"ending on degree {degree}"))
    return found


def melody_candidates(model: Model, edits: dict[str, dict[str, Any]]) -> list[Suggestion]:
    """Readings of hand edits to melody tracks, before any is lowered."""
    from pypulang.lift import Suggestion

    groups: dict[tuple[str, str, str], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for loc, entry in edits.items():
        chain = model.note(loc)
        if chain is not None:
            groups[(chain.tag, chain.section, chain.track)].append((loc, entry))

    piece = model.intent
    motifs = piece.motifs()
    out: list[Suggestion] = []
    for (tag, section, track), items in groups.items():
        section_op = model._intent_section(section)  # noqa: SLF001 — the model's own index
        if section_op is None:
            continue
        track_op = next((t for t in section_op.tracks() if t.track.data == track), None)
        melody = (
            next((o for o in track_op.body.block.ops if isinstance(o, intent.MelodyOp)), None)
            if track_op is not None
            else None
        )
        if melody is None:
            continue
        key = section_op.key.data if section_op.key is not None else piece.key.data
        meter = section_op.meter.data if section_op.meter is not None else piece.meter.data
        length = section_op.bars.value.data * meter.beats_per_bar
        traced = realize_melody(melody, section, track, key, meter, length, motifs)
        located = _locations(traced, tag, track, meter.beats_per_bar, length)
        octave = track_op.octave.value.data

        by_placement: dict[int, list[_Edited]] = defaultdict(list)
        for loc, entry in items:
            found = located.get(loc)
            if found is None:
                continue
            note, trace = found
            one = _Edited(loc, trace, note, entry)
            if not entry.get("deleted"):
                if entry["note"][0] == entry["base"][0]:
                    # Moved in time only: the degree stays the one written, not the
                    # one the chord fitted it to.
                    one.accidental = trace.note.accidental
                else:
                    new_step, one.accidental = degree_of(entry["note"][0] - 12 * octave, key)
                    one.step = new_step - degree_of(trace.written, key)[0]
                one.moved = _quantize(Fraction(entry["note"][1] - entry["base"][1], PPQ))
                one.stretched = _quantize(Fraction(entry["note"][2] - entry["base"][2], PPQ))
            by_placement[trace.placement].append(one)

        phrase = melody.phrase.data
        placements = parse_phrase(phrase)
        for index, edited in by_placement.items():
            placement = placements[index]
            if placement.motif is None or placement.motif not in motifs:
                continue
            all_of_it = [t for n, t in traced if t.placement == index and n.start < length]
            rewritten = _motif_reading(
                placement.motif,
                motifs[placement.motif],
                placement,
                edited,
                all_of_it[-1] if all_of_it else None,
            )
            if rewritten is not None:
                out.append(
                    Suggestion(
                        [
                            Edit(
                                "intent",
                                f"motif/{placement.motif}",
                                "notes",
                                rewritten,
                                motifs[placement.motif],
                            )
                        ],
                        f"the edits rewrite the motif {placement.motif}: change it everywhere it is used",
                    )
                )
            for new_phrase, what in _phrase_readings(phrase, index, all_of_it, edited, key):
                out.append(
                    Suggestion(
                        [Edit("intent", f"{section}/{track}", "melody", new_phrase, phrase)],
                        f"this statement of {placement.motif} moved {what}: change the {track} "
                        f"phrase in every {section}",
                    )
                )
    return out
