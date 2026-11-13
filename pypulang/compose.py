"""
What the compose view shows: the song as its form, its sections and parts, its
motifs and where each is used, the notes every part plays, and what a pending
edit would change.

The compose view is kaiDAW's full-screen mode for writing above the notes. Its
page asks `pulang serve` for these as JSON. A pending edit is compiled beside the
song, never saved, and compared with it note by note, so the page can draw the
change in the piano roll and on the staff, and light up every place it reaches,
before anything is applied.

Everything here is read from a song compiled to the score stage: the notes as
written, before swing and humanizing move them, which is what a staff shows and
what a change to the writing changes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from xdsl.dialects.builtin import ModuleOp

from pypulang.compiler.dialects import intent, score
from pypulang.compiler.edits import chord_starts, position, section_chart, track_value
from pypulang.compiler.locs import loc_key
from pypulang.compiler.pipeline import CompileResult
from pypulang.compiler.spelling import midi_of
from pypulang.harmony import chord_symbol
from pypulang.ir.intent import Key
from pypulang.motifs import (
    MotifNote,
    Placement,
    develop,
    format_motif,
    format_phrase,
    parse_motif,
    parse_phrase,
)
from pypulang.notation import Engraved, Staff, StaffNote, engrave
from pypulang.resolution import resolve_chord
from pypulang.scales import get_scale_pitches, pitch_class_to_semitone

ADDED = "#3fae5a"  # a note an edit adds, on the staff


def _top(module: ModuleOp, kind: type) -> Any:
    return next(o for o in module.body.block.ops if isinstance(o, kind))


def _key_text(key: Key) -> str:
    return f"{key.root} {key.mode.replace('_', ' ')}"


def _num(value: Fraction) -> float | int:
    return int(value) if value.denominator == 1 else float(value)


@dataclass
class Note:
    pitch: int
    start: Fraction  # beats from the start of its section occurrence
    dur: Fraction
    vel: int
    voice: int
    id: str  # its location, as the lock and the inspector name it

    def json(self) -> dict[str, Any]:
        return {
            "p": self.pitch,
            "s": _num(self.start),
            "d": _num(self.dur),
            "v": self.vel,
            "voice": self.voice,
            "id": self.id,
        }

    @property
    def sound(self) -> tuple[int, Fraction, Fraction]:
        return self.pitch, self.start, self.dur


@dataclass
class Occurrence:
    tag: str  # "chorus#2"
    section: str
    number: int
    start: Fraction  # beats from the top of the song
    bars: int
    first_bar: int
    key: Key
    meter: Any

    @property
    def length(self) -> Fraction:
        return self.bars * self.meter.beats_per_bar


class Snapshot:
    """A song compiled to the score, indexed by section occurrence and part."""

    def __init__(self, result: CompileResult):
        self.result = result
        self.intent: intent.PieceOp = _top(result.stages["intent"], intent.PieceOp)
        self.score: score.ScoreOp = _top(result.stages["score"], score.ScoreOp)
        self.occurrences = [
            Occurrence(
                s.tag,
                s.section.data,
                s.occurrence.value.data,
                s.start.data,
                s.bars.value.data,
                s.start_bar.value.data,
                s.key.data,
                s.meter.data,
            )
            for s in self.score.sections()
        ]
        self.by_tag = {o.tag: o for o in self.occurrences}
        self.roles = {p.part.data: p.role.data for p in self.score.parts()}
        self.notes: dict[tuple[str, str], list[Note]] = {}
        for part in self.score.parts():
            for bar in part.bars():
                for n in bar.notes():
                    loc = loc_key(n.location)
                    tag, _, rest = loc.partition("/")
                    track = rest.partition("/")[0]
                    occurrence = self.by_tag.get(tag)
                    if occurrence is None:
                        continue
                    self.notes.setdefault((tag, track), []).append(
                        Note(
                            midi_of(n.pitch.data),
                            bar.start.data + n.beat.data - occurrence.start,
                            n.dur.data,
                            n.vel.value.data,
                            n.voice.value.data,
                            loc,
                        )
                    )
        for notes in self.notes.values():
            notes.sort(key=lambda n: (n.start, n.pitch))

    # -- the intent the score came from ------------------------------------------------

    def section_op(self, name: str) -> intent.SectionOp | None:
        return next((s for s in self.intent.sections() if s.section.data == name), None)

    def motifs(self) -> dict[str, str]:
        return self.intent.motifs()

    def chords(self, tag: str) -> list[dict[str, Any]]:
        """The chords of one occurrence: where each starts, as played."""
        occurrence = self.by_tag[tag]
        out = []
        for chord in self.score.chords():
            at = chord.at.data - occurrence.start
            if 0 <= at < occurrence.length:
                out.append(
                    {
                        "at": _num(at),
                        "dur": _num(chord.dur.data),
                        "symbol": chord_symbol(chord.chord.data, chord.key.data),
                        "position": position(at, occurrence.meter),
                        "tones": sorted(
                            {p % 12 for p in resolve_chord(chord.chord.data, chord.key.data)}
                        ),
                    }
                )
        return out

    def tracks(self, name: str) -> list[dict[str, Any]]:
        """A section's parts as written: what each plays and how."""
        section = self.section_op(name)
        if section is None:
            return []
        out = []
        for track in section.tracks():
            melody = track_value(track, "melody")
            pattern = track_value(track, "pattern")
            entry: dict[str, Any] = {
                "track": track.track.data,
                "role": track.role.data,
                "plays": "melody" if melody else "pattern" if pattern else "notes",
                "velocity": track_value(track, "velocity"),
                "voicing": track_value(track, "voicing"),
                "muted": track_value(track, "muted"),
            }
            if melody:
                entry["melody"] = {"text": melody, "chips": chips(melody, self.motifs())}
            if pattern:
                entry["pattern"] = pattern_text(pattern)
            out.append(entry)
        return out

    # -- the views ---------------------------------------------------------------------

    def song(self) -> dict[str, Any]:
        """The whole song, for the map at the top of the page."""
        piece = self.intent
        tempos = sorted((t.at.data, t.bpm.value.data) for t in self.score.tempos())

        def tempo_at(beat: Fraction) -> float:
            bpm = piece.tempo.value.data
            for at, value in tempos:
                if at <= beat:
                    bpm = value
            return round(bpm, 2)

        sections = {}
        for section in piece.sections():
            name = section.section.data
            key = section.key.data if section.key is not None else piece.key.data
            sections[name] = {
                "bars": section.bars.value.data,
                "key": _key_text(key),
                "chart": section_chart(section, piece) if section.harmony() is not None else "",
                "derived": section.derived_from.data if section.derived_from is not None else None,
                "tempo": section.tempo.value.data if section.tempo is not None else None,
            }
        order = list(self.roles)
        activity: dict[str, dict[str, int]] = {}
        for (tag, track), notes in self.notes.items():
            activity.setdefault(tag, {})[track] = len(notes)
        return {
            "title": piece.title.data if hasattr(piece, "title") else "",
            "key": _key_text(piece.key.data),
            "tempo": piece.tempo.value.data,
            "meter": f"{piece.meter.data.numerator}/{piece.meter.data.denominator}",
            "ppq": 960,
            "form": [
                {
                    "tag": o.tag,
                    "section": o.section,
                    "number": o.number,
                    "start": _num(o.start),
                    "bars": o.bars,
                    "firstBar": o.first_bar,
                    "beatsPerBar": _num(o.meter.beats_per_bar),
                    "meter": f"{o.meter.numerator}/{o.meter.denominator}",
                    "key": _key_text(o.key),
                    "tempo": tempo_at(o.start),
                    "chords": [c["symbol"] for c in self.chords(o.tag)],
                }
                for o in self.occurrences
            ],
            "sections": sections,
            "tracks": [{"name": t, "role": self.roles[t]} for t in order],
            "activity": activity,
            "motifs": self.motif_list(),
        }

    def motif_list(self) -> list[dict[str, Any]]:
        """Every motif, its notes in degrees, and each place a melody uses it."""
        uses: dict[str, list[dict[str, Any]]] = {}
        for section in self.intent.sections():
            for track in section.tracks():
                melody = track_value(track, "melody")
                if not melody:
                    continue
                for chip in chips(melody, self.motifs()):
                    if chip["motif"] is None:
                        continue
                    uses.setdefault(chip["motif"], []).append(
                        {
                            "section": section.section.data,
                            "track": track.track.data,
                            "index": chip["index"],
                            "text": chip["text"],
                            "start": chip["start"],
                            "length": chip["length"],
                        }
                    )
        out = []
        for name, text in self.motifs().items():
            motif = parse_motif(text)
            out.append(
                {
                    "name": name,
                    "text": text,
                    "length": _num(motif.length),
                    "notes": [_motif_note(n) for n in motif.notes],
                    "uses": uses.get(name, []),
                }
            )
        return out

    def section(self, tag: str) -> dict[str, Any]:
        """One occurrence of a section: its chords, its parts and their notes."""
        o = self.by_tag[tag]
        written = self.tracks(o.section)
        parts = []
        seen = set()
        for entry in written:
            name = entry["track"]
            seen.add(name)
            notes = self.notes.get((tag, name), [])
            parts.append({**entry, "notes": [n.json() for n in notes]})
        for (
            t,
            name,
        ), notes in self.notes.items():  # parts the section did not write, such as fills
            if t == tag and name not in seen:
                parts.append(
                    {
                        "track": name,
                        "role": self.roles.get(name, ""),
                        "plays": "notes",
                        "notes": [n.json() for n in notes],
                    }
                )
        section = self.section_op(o.section)
        return {
            "tag": tag,
            "section": o.section,
            "number": o.number,
            "start": _num(o.start),
            "bars": o.bars,
            "firstBar": o.first_bar,
            "beatsPerBar": _num(o.meter.beats_per_bar),
            "meter": f"{o.meter.numerator}/{o.meter.denominator}",
            "key": _key_text(o.key),
            "scale": sorted(
                (pitch_class_to_semitone(o.key.root) + step) % 12
                for step in get_scale_pitches(o.key)
            ),
            "chart": section_chart(section, self.intent) if section is not None else "",
            "chordStarts": sorted(
                chord_starts(section, self.intent.meter.data) if section is not None else {}
            ),
            "chords": self.chords(tag),
            "parts": parts,
        }

    def staff(self, tag: str, track: str, colors: dict[str, str] | None = None) -> Engraved:
        """One part of one occurrence on a staff, with the chords over it."""
        o = self.by_tag[tag]
        colors = colors or {}
        notes = [
            StaffNote(n.pitch, n.start, n.dur, n.id, colors.get(n.id), n.voice)
            for n in self.notes.get((tag, track), [])
        ]
        chords = [(Fraction(c["at"]), c["symbol"]) for c in self.chords(tag)]
        return engrave(Staff(notes, o.bars, o.key, o.meter, o.first_bar, chords))


def _motif_note(note: MotifNote) -> dict[str, Any]:
    return {
        "step": note.step,
        "acc": note.accidental,
        "s": _num(note.start),
        "d": _num(note.dur),
        "accent": 1 if note.velocity_scale > 1 else -1 if note.velocity_scale < 1 else 0,
        "staccato": note.articulation == "staccato",
    }


def pattern_text(pattern: dict[str, Any]) -> str:
    params = pattern.get("params") or {}
    shown = ", ".join(f"{k}={v}" for k, v in params.items())
    return f"{pattern['kind']}({shown})"


# -- melody as chips -------------------------------------------------------------------


def chips(phrase: str, motifs: dict[str, str]) -> list[dict[str, Any]]:
    """
    A phrase's placements as the page draws them: each one's text, its motif, and
    the beats it spans from the start of the section.
    """
    parsed = {}
    out = []
    at = Fraction(0)
    for index, placement in enumerate(parse_phrase(phrase)):
        text = format_phrase([placement])
        if placement.motif is None:
            out.append(_chip(index, text, None, at, placement.rest))
            at += placement.rest
            continue
        if placement.motif not in motifs:
            out.append(_chip(index, text, placement.motif, at, Fraction(0), missing=True))
            continue
        if placement.motif not in parsed:
            parsed[placement.motif] = parse_motif(motifs[placement.motif])
        motif = parsed[placement.motif]
        for op, arg in placement.ops:
            if op not in ("^", "v"):
                motif = develop(motif, op, arg)
        out.append(_chip(index, text, placement.motif, at, motif.length))
        at += motif.length
    return out


def _chip(
    index: int, text: str, motif: str | None, at: Fraction, length: Fraction, missing: bool = False
) -> dict[str, Any]:
    chip = {"index": index, "text": text, "motif": motif, "start": _num(at), "length": _num(length)}
    if missing:
        chip["missing"] = True
    return chip


_TOGGLES = ("inv", "rev")


def phrase_op(phrase: str, index: int, op: str, arg: str | None = None) -> str:
    """
    A phrase with one placement changed, the gestures the chips offer:

        up, down      one scale step higher or lower (a sequence)
        octave_up, octave_down
        inv, rev      turn the inversion or the reversal on or off
        vary          ornament it, or ornament it another way
        plain         take every development off
        motif         use another motif (`arg`), keeping the developments
        first, last   keep only the first or last `arg` notes ("" for all)
        end           end on degree `arg` ("" to stop)
        insert        put `arg` (a placement, such as "hook" or "rest 2") after this one
        delete
        left, right   swap with the neighbour

    Raises:
        ValueError: On an index out of range or a placement that cannot be read
    """
    placements = parse_phrase(phrase)
    if not (0 <= index < len(placements)) and not (op == "insert" and index == -1):
        raise ValueError(f"no placement {index} in {phrase!r}")
    if op == "insert":
        placements[index + 1 : index + 1] = parse_phrase(arg or "")
        return format_phrase(placements)
    if op == "delete":
        del placements[index]
        return format_phrase(placements)
    if op in ("left", "right"):
        other = index - 1 if op == "left" else index + 1
        if 0 <= other < len(placements):
            placements[index], placements[other] = placements[other], placements[index]
        return format_phrase(placements)
    placement = placements[index]
    if placement.motif is None:
        if op in ("up", "down", "longer", "shorter"):
            raise ValueError("a rest has no notes to move")
        raise ValueError(f"cannot {op} a rest")
    ops = list(placement.ops)
    if op in ("up", "down"):
        steps = _steps(ops) + (1 if op == "up" else -1)
        ops = [o for o in ops if o[0] not in ("+", "-")]
        if steps:
            ops.insert(0, ("+" if steps > 0 else "-", str(abs(steps))))
    elif op in ("octave_up", "octave_down"):
        octave = sum(1 if o == "^" else -1 for o, _ in ops if o in ("^", "v"))
        octave += 1 if op == "octave_up" else -1
        ops = [o for o in ops if o[0] not in ("^", "v")]
        ops.extend([("^" if octave > 0 else "v", None)] * abs(octave))
    elif op in _TOGGLES:
        if any(o == op for o, _ in ops):
            ops = [o for o in ops if o[0] != op]
        else:
            ops.append((op, None))
    elif op == "vary":
        seeds = [int(a) for o, a in ops if o == "vary" and a and a.isdigit()]
        ops = [o for o in ops if o[0] != "vary"]
        ops.append(("vary", str((seeds[0] + 1) if seeds else 1)))
    elif op == "plain":
        ops = []
    elif op == "motif":
        if not arg:
            raise ValueError("which motif?")
        placement = Placement(arg, placement.ops)
    elif op in ("first", "last", "end"):
        ops = [o for o in ops if o[0] != op]
        if arg:
            ops.append((op, arg))
    else:
        raise ValueError(f"no chip gesture {op!r}")
    placements[index] = Placement(placement.motif, tuple(ops))
    return format_phrase(placements)


def _steps(ops: list[tuple[str, str | None]]) -> int:
    return sum(int(a or 0) * (1 if o == "+" else -1) for o, a in ops if o in ("+", "-"))


def motif_text(notes: list[dict[str, Any]], length: float | str) -> str:
    """
    Motif notes as the page edits them, written back as motif text.

    Raises:
        ValueError: When the notes overlap or a length has no note value
    """
    parsed = [
        MotifNote(
            int(n["step"]),
            int(n.get("acc", 0)),
            Fraction(str(n["s"])),
            Fraction(str(n["d"])),
            Fraction(5, 4)
            if n.get("accent", 0) > 0
            else Fraction(3, 5)
            if n.get("accent", 0) < 0
            else Fraction(1),
            "staccato" if n.get("staccato") else None,
        )
        for n in notes
    ]
    text = format_motif(parsed, Fraction(str(length)))
    if text is None:
        raise ValueError("those notes overlap, or a length has no note value")
    parse_motif(text)
    return text


# -- what an edit changes ------------------------------------------------------------


@dataclass
class Change:
    """The notes an edit adds and removes, by section occurrence and part."""

    parts: dict[tuple[str, str], tuple[list[Note], list[Note]]] = field(default_factory=dict)

    @property
    def added(self) -> int:
        return sum(len(a) for a, _ in self.parts.values())

    @property
    def removed(self) -> int:
        return sum(len(r) for _, r in self.parts.values())

    def tags(self) -> list[str]:
        seen: list[str] = []
        for tag, _ in self.parts:
            if tag not in seen:
                seen.append(tag)
        return seen

    def json(self) -> dict[str, Any]:
        by_tag: dict[str, dict[str, Any]] = {}
        for (tag, track), (added, removed) in self.parts.items():
            by_tag.setdefault(tag, {})[track] = {
                "added": [n.json() for n in added],
                "removed": [n.json() for n in removed],
            }
        return {"added": self.added, "removed": self.removed, "tags": self.tags(), "parts": by_tag}


def compare(before: Snapshot, after: Snapshot) -> Change:
    """What changed between two compiles of a song, note by note."""
    change = Change()
    order = [o.tag for o in after.occurrences]
    keys = sorted(
        set(before.notes) | set(after.notes),
        key=lambda k: (order.index(k[0]) if k[0] in order else len(order), k[1]),
    )
    for key in keys:
        old = before.notes.get(key, [])
        new = after.notes.get(key, [])
        left = Counter(n.sound for n in old)
        right = Counter(n.sound for n in new)
        gone, came = left - right, right - left
        if not gone and not came:
            continue
        added = _take(new, came)
        removed = _take(old, gone)
        change.parts[key] = (added, removed)
    return change


def _take(notes: list[Note], wanted: Counter) -> list[Note]:
    left = Counter(wanted)
    out = []
    for note in notes:
        if left[note.sound] > 0:
            left[note.sound] -= 1
            out.append(note)
    return out
