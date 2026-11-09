"""
Edits made above the notes: a chord, a voicing, a track's settings.

A DAW edit is kept at the level it was made at. Moving a note is a note edit and
lives in `overrides.notes`. Changing the chord a section plays is not a note edit:
it is an edit of the intent IR, kept as one and applied by a pass, so every note
the chord produces follows it and the source file is never rewritten.

Each edit names its target the way locations do, by musical position:

    level   target                       field
    intent  "verse/harmony@3+0"          chord      the chord starting at bar 3, beat 0
    intent  "verse/keys"                 voicing | octave | velocity | muted | pattern
    score   "verse#2/harmony@3+0"        chord      the same chord, in the 2nd verse only
    score   "verse#2/keys/c4"            pitches    one chord's exact notes, for one part

An intent edit changes every occurrence of its section, because the intent IR
describes a section once; a score edit changes one occurrence. `base` is what the
source gave when the edit was made. When the source moves underneath an edit, the
edit still applies and is reported as stale, as a note edit is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from xdsl.context import Context
from xdsl.dialects.builtin import IntegerAttr, ModuleOp, StringAttr, i64
from xdsl.passes import ModulePass

from pypulang.compiler.dialects import intent, score
from pypulang.compiler.dialects.mus import ChordAttr, format_rational, from_attr, to_attr
from pypulang.compiler.locs import loc_key
from pypulang.compiler.passes.lower_intent import _chord_spans
from pypulang.harmony import chord_symbol, parse_chord_symbol
from pypulang.ir.intent import Key, TimeSignature
from pypulang.resolution import resolve_chord

LEVELS = ("intent", "score")
TRACK_FIELDS = ("voicing", "octave", "velocity", "muted", "pattern")


@dataclass
class Edit:
    level: str
    target: str
    field: str
    value: Any
    base: Any = None

    @property
    def key(self) -> str:
        """One string naming what is edited, for listing and dropping."""
        return f"{self.level}:{self.target}:{self.field}"

    def to_json(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "target": self.target,
            "field": self.field,
            "value": self.value,
            "base": self.base,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Edit:
        return cls(data["level"], data["target"], data["field"], data["value"], data.get("base"))


@dataclass
class EditReport:
    """What happened to each edit on one compile."""

    applied: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    orphaned: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        return [
            *(f"Stale edit: {s}" for s in self.stale),
            *(f"Orphaned edit: {s}" for s in self.orphaned),
        ]


def position(offset: Fraction, meter: TimeSignature) -> str:
    """Beats from a section's start as "bar+beat", bars counted from 1."""
    bar = int(offset // meter.beats_per_bar)
    return f"{bar + 1}+{format_rational(offset - bar * meter.beats_per_bar)}"


def _parse_target(target: str) -> tuple[str, int | None, str]:
    """ "verse#2/harmony@3+0" -> ("verse", 2, "harmony@3+0")."""
    head, _, rest = target.partition("/")
    name, hash_, occurrence = head.partition("#")
    return name, int(occurrence) if hash_ else None, rest


def chord_starts(section: intent.SectionOp, piece_meter: TimeSignature) -> dict[str, int]:
    """Each chord's position in a section, mapped to its index in the harmony."""
    harmony = section.harmony()
    if harmony is None:
        return {}
    meter = section.meter.data if section.meter is not None else piece_meter
    beats = section.bars.value.data * meter.beats_per_bar
    return {
        position(at, meter): index
        for index, (_, at, _) in enumerate(_chord_spans(harmony, beats, meter))
    }


def track_value(track: intent.TrackOp, name: str) -> Any:
    """A track setting as an edit carries it."""
    if name == "voicing":
        return track.voicing.data if track.voicing is not None else None
    if name in ("octave", "velocity"):
        return getattr(track, name).value.data
    if name == "muted":
        return bool(track.muted.value.data)
    if name == "pattern":
        pattern = next((o for o in track.body.block.ops if isinstance(o, intent.PatternOp)), None)
        if pattern is None:
            return None
        return {"kind": pattern.kind.data, "params": from_attr(pattern.params)}
    raise ValueError(f"No track setting {name!r}; settings are {', '.join(TRACK_FIELDS)}")


def _set_track(track: intent.TrackOp, name: str, value: Any) -> None:
    if name == "voicing":
        if value in (None, ""):
            track.properties.pop("voicing", None)
        else:
            track.properties["voicing"] = StringAttr(str(value))
    elif name in ("octave", "velocity"):
        track.properties[name] = IntegerAttr(int(value), i64)
    elif name == "muted":
        track.properties["muted"] = IntegerAttr(int(bool(value)), i64)
    elif name == "pattern":
        pattern = next((o for o in track.body.block.ops if isinstance(o, intent.PatternOp)), None)
        if pattern is None:
            raise ValueError("this track plays written notes, not a pattern")
        pattern.properties["kind"] = StringAttr(value["kind"])
        pattern.properties["params"] = to_attr(value.get("params", {}))


def _piece(module: ModuleOp) -> intent.PieceOp:
    return next(o for o in module.body.block.ops if isinstance(o, intent.PieceOp))


def _intent_section(piece: intent.PieceOp, name: str) -> intent.SectionOp | None:
    return next((s for s in piece.sections() if s.section.data == name), None)


def _section_key(piece: intent.PieceOp, section: intent.SectionOp) -> Key:
    return section.key.data if section.key is not None else piece.key.data


def current_value(module: ModuleOp, edit: Edit) -> tuple[bool, Any]:
    """
    What the source gives at an intent edit's target, before the edit.

    Returns:
        Whether the target exists, and its value
    """
    piece = _piece(module)
    name, _, rest = _parse_target(edit.target)
    section = _intent_section(piece, name)
    if section is None:
        return False, None
    if rest.startswith("harmony@"):
        index = chord_starts(section, piece.meter.data).get(rest.removeprefix("harmony@"))
        if index is None:
            return False, None
        chord = section.harmony().changes()[index][0]
        return True, chord_symbol(chord, _section_key(piece, section))
    track = next((t for t in section.tracks() if t.track.data == rest), None)
    if track is None:
        return False, None
    return True, track_value(track, edit.field)


@dataclass(frozen=True)
class ApplyIntentEdits(ModulePass):
    """Apply the intent-level edits, after the song's own intent passes."""

    name = "apply-intent-edits"
    edits: tuple[Edit, ...] = ()
    report: EditReport = field(default_factory=EditReport)

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        piece = _piece(op)
        for edit in self.edits:
            if edit.level != "intent":
                continue
            exists, now = current_value(op, edit)
            if not exists:
                self.report.orphaned.append(f"{edit.key}: the source has no such place")
                continue
            if now != edit.base:
                self.report.stale.append(
                    f"{edit.key}: edited when the source gave {edit.base!r}, source now gives {now!r}"
                )
            name, _, rest = _parse_target(edit.target)
            section = _intent_section(piece, name)
            if rest.startswith("harmony@"):
                index = chord_starts(section, piece.meter.data)[rest.removeprefix("harmony@")]
                harmony = section.harmony()
                chords = list(harmony.chords.data)
                chords[index] = ChordAttr(
                    parse_chord_symbol(str(edit.value), _section_key(piece, section))
                )
                harmony.properties["chords"] = type(harmony.chords)(chords)
            else:
                track = next(t for t in section.tracks() if t.track.data == rest)
                _set_track(track, edit.field, edit.value)
            self.report.applied.append(edit.key)


def _score_section(top: score.ScoreOp, name: str, occurrence: int) -> score.SectionOp | None:
    return next(
        (
            s
            for s in top.sections()
            if s.section.data == name and s.occurrence.value.data == occurrence
        ),
        None,
    )


def _absolute(section: score.SectionOp, where: str) -> Fraction:
    bar, _, beat = where.partition("+")
    return section.start.data + (int(bar) - 1) * section.meter.data.beats_per_bar + Fraction(beat)


def score_chord_at(top: score.ScoreOp, target: str) -> score.ChordOp | None:
    name, occurrence, rest = _parse_target(target)
    if occurrence is None or not rest.startswith("harmony@"):
        return None
    section = _score_section(top, name, occurrence)
    if section is None:
        return None
    at = _absolute(section, rest.removeprefix("harmony@"))
    return next((c for c in top.chords() if c.at.data == at), None)


def score_slot(top: score.ScoreOp, target: str) -> score.SlotOp | None:
    for part in top.parts():
        for slot in part.slots():
            if loc_key(slot.location) == target:
                return slot
    return None


@dataclass(frozen=True)
class ApplyScoreEdits(ModulePass):
    """
    Apply score-level edits of one kind.

    Chords run before voice leading, so the new chord is voiced in context with its
    neighbours. Pitches run after it, so an exact voicing someone chose is kept.
    """

    name = "apply-score-edits"
    edits: tuple[Edit, ...] = ()
    fields: tuple[str, ...] = ("chord",)
    report: EditReport = field(default_factory=EditReport)

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        top = next(o for o in op.body.block.ops if isinstance(o, score.ScoreOp))
        for edit in self.edits:
            if edit.level != "score" or edit.field not in self.fields:
                continue
            if edit.field == "chord":
                self._chord(top, edit)
            elif edit.field == "pitches":
                self._pitches(top, edit)
            else:
                self.report.orphaned.append(f"{edit.key}: no score setting {edit.field!r}")

    def _chord(self, top: score.ScoreOp, edit: Edit) -> None:
        chord_op = score_chord_at(top, edit.target)
        if chord_op is None:
            self.report.orphaned.append(f"{edit.key}: no chord starts there")
            return
        key: Key = chord_op.key.data
        now = chord_symbol(chord_op.chord.data, key)
        if now != edit.base:
            self.report.stale.append(
                f"{edit.key}: edited when the source gave {edit.base!r}, source now gives {now!r}"
            )
        new = parse_chord_symbol(str(edit.value), key)
        at = chord_op.at.data
        chord_op.properties["chord"] = ChordAttr(new)
        name, occurrence, _ = _parse_target(edit.target)
        tag = f"{name}#{occurrence}"
        for part in top.parts():
            for slot in part.slots():
                if slot.section.data != tag:
                    continue
                if slot.start.data == at:
                    slot.properties["chord"] = ChordAttr(new)
                    slot.set_pitches(resolve_chord(new, key, octave=4))
                elif slot.start.data + slot.dur.data == at and slot.next_chord is not None:
                    slot.properties["next_chord"] = ChordAttr(new)
        self.report.applied.append(edit.key)

    def _pitches(self, top: score.ScoreOp, edit: Edit) -> None:
        slot = score_slot(top, edit.target)
        if slot is None:
            self.report.orphaned.append(f"{edit.key}: no such chord in that part")
            return
        if slot.pitch_list() != edit.base:
            self.report.stale.append(
                f"{edit.key}: edited when the source gave {edit.base}, "
                f"source now gives {slot.pitch_list()}"
            )
        slot.set_pitches([int(p) for p in edit.value])
        self.report.applied.append(edit.key)
