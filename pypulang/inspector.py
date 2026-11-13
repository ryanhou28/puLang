"""
What produced a note: the chain from a DAW note up through every IR level.

A note in kaiDAW is found by its id in the song's lock, which gives its location,
such as "verse#2/keys/3+1/2/v1". The location then finds the note at each level: the
event note after performance passes, the score note, the chord slot that voiced it
and the chord it voices, and at the top the section and the track settings that
made the slot. Each level is shown with the edits that can be made there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from xdsl.dialects.builtin import ModuleOp

from pypulang.backends.kaidaw.state import Lock, Overrides
from pypulang.compiler.dialects import event, intent, score
from pypulang.compiler.edits import chord_starts, position, track_value
from pypulang.compiler.locs import loc_key
from pypulang.compiler.pipeline import CompileResult
from pypulang.compiler.spelling import spell
from pypulang.harmony import chord_symbol
from pypulang.ir.intent import Key
from pypulang.motifs import parse_phrase

_LOC_RE = re.compile(r"^([^#/]+)#(\d+)/([^/]+)/(\d+)\+(\d+(?:/\d+)?)/(\w+)$")


@dataclass
class ChordInfo:
    position: str  # "bar+beat" within the section
    symbol: str  # as this occurrence plays it
    written: str | None  # as the section is written, before any score edit

    def intent_target(self, section: str) -> str:
        return f"{section}/harmony@{self.position}"

    def score_target(self, tag: str) -> str:
        return f"{tag}/harmony@{self.position}"


@dataclass
class SlotInfo:
    target: str  # "verse#2/keys/c4"
    kind: str
    chord: str
    pitches: list[int]  # as heard, octave included
    octave: int
    voicing: str | None


@dataclass
class TrackInfo:
    target: str  # "verse/keys"
    role: str
    settings: dict[str, Any]
    plays: str  # "pattern", "melody" or "notes"
    motifs: dict[str, str] = field(default_factory=dict)  # those its melody uses


@dataclass
class NoteChain:
    loc: str
    tag: str  # "verse#2"
    section: str
    track: str
    where: str  # "bar 3, beat 1/2, voice v1"
    daw: list[int] | None = None
    event: list[Any] | None = None
    score: str | None = None
    slot: SlotInfo | None = None
    chord: ChordInfo | None = None
    override: dict[str, Any] | None = None


@dataclass
class ClipView:
    """Everything shown for one clip: its section occurrence, its track, and notes."""

    key: str
    tag: str
    section: str
    track: str
    bars: int
    key_name: str
    meter: str
    chords: list[ChordInfo] = field(default_factory=list)
    track_info: TrackInfo | None = None
    slots: list[SlotInfo] = field(default_factory=list)
    notes: list[NoteChain] = field(default_factory=list)


def parse_loc(loc: str) -> tuple[str, int, str, int, Fraction, str] | None:
    """ "verse#2/keys/3+1/2/v1" -> ("verse", 2, "keys", 3, 1/2, "v1"); None for others."""
    m = _LOC_RE.match(loc)
    if m is None:
        return None
    return m[1], int(m[2]), m[3], int(m[4]), Fraction(m[5]), m[6]


def _top(module: ModuleOp, kind: type) -> Any:
    return next(o for o in module.body.block.ops if isinstance(o, kind))


def voiced_module(result: CompileResult) -> ModuleOp:
    """The score after voice leading and score edits, before patterns become notes."""
    names = [name for name, _ in result.trace]
    if "realize-patterns" not in names:
        raise ValueError("compile with keep_trace=True to inspect")
    return result.trace[names.index("realize-patterns") - 1][1]


class Model:
    """A compiled song, indexed for inspection."""

    def __init__(self, result: CompileResult, lock: Lock, overrides: Overrides):
        self.result = result
        self.lock = lock
        self.overrides = overrides
        self.intent = _top(result.stages["intent"], intent.PieceOp)
        self.voiced = _top(voiced_module(result), score.ScoreOp)
        self.final = _top(result.stages["score"], score.ScoreOp)
        self.events = {
            loc_key(n.location): (t.track.data, n)
            for t in _top(result.stages["event"], event.StreamOp).tracks()
            for n in t.notes()
        }
        self.score_notes = {
            loc_key(n.location): n
            for part in self.final.parts()
            for bar in part.bars()
            for n in bar.notes()
        }
        self.by_note_id = {entry["id"]: loc for loc, entry in lock.notes.items()}
        self.by_clip_id = {info["id"]: key for key, info in lock.clips.items()}

    # -- the levels, for one place -----------------------------------------------------

    def _section(self, name: str, occurrence: int) -> score.SectionOp | None:
        return next(
            (
                s
                for s in self.voiced.sections()
                if s.section.data == name and s.occurrence.value.data == occurrence
            ),
            None,
        )

    def _intent_section(self, name: str) -> intent.SectionOp | None:
        return next((s for s in self.intent.sections() if s.section.data == name), None)

    def chords(self, name: str, occurrence: int) -> list[ChordInfo]:
        """The chords of one occurrence of a section, as played and as written."""
        section = self._section(name, occurrence)
        if section is None:
            return []
        start, length = (
            section.start.data,
            section.bars.value.data * section.meter.data.beats_per_bar,
        )
        written: dict[str, str] = {}
        source = self._intent_section(name)
        if source is not None and source.harmony() is not None:
            changes = source.harmony().changes()
            key = source.key.data if source.key is not None else self.intent.key.data
            for where, index in chord_starts(source, self.intent.meter.data).items():
                written[where] = chord_symbol(changes[index][0], key)
        result = []
        for chord in self.voiced.chords():
            if start <= chord.at.data < start + length:
                where = position(chord.at.data - start, section.meter.data)
                result.append(
                    ChordInfo(
                        where, chord_symbol(chord.chord.data, chord.key.data), written.get(where)
                    )
                )
        return result

    def track(self, name: str, track: str) -> TrackInfo | None:
        section = self._intent_section(name)
        op = next((t for t in section.tracks() if t.track.data == track), None) if section else None
        if op is None:
            return None
        pattern = track_value(op, "pattern")
        melody = track_value(op, "melody")
        settings = {f: track_value(op, f) for f in ("voicing", "octave", "velocity", "muted")}
        plays = "notes"
        motifs: dict[str, str] = {}
        if pattern is not None:
            settings["pattern"] = pattern
            plays = "pattern"
        if melody is not None:
            settings["melody"] = melody
            plays = "melody"
            defined = self.intent.motifs()
            for placement in parse_phrase(melody):
                if placement.motif in defined:
                    motifs[placement.motif] = defined[placement.motif]
        return TrackInfo(f"{name}/{track}", op.role.data, settings, plays, motifs)

    def slots(self, tag: str, track: str) -> list[SlotInfo]:
        part = next((p for p in self.voiced.parts() if p.part.data == track), None)
        if part is None:
            return []
        return [
            SlotInfo(
                loc_key(slot.location),
                slot.kind.data,
                chord_symbol(slot.chord.data, slot.key.data),
                [p + 12 * slot.octave.value.data for p in slot.pitch_list()],
                slot.octave.value.data,
                slot.voicing.data if slot.voicing is not None else None,
            )
            for slot in part.slots()
            if slot.section.data == tag
        ]

    def note(self, loc: str) -> NoteChain | None:
        parsed = parse_loc(loc)
        if parsed is None:
            return None
        name, occurrence, track, bar, beat, voice = parsed
        tag = f"{name}#{occurrence}"
        chain = NoteChain(loc, tag, name, track, f"bar {bar}, beat {beat}, voice {voice}")
        entry = self.lock.notes.get(loc)
        chain.daw = entry["note"] if entry else None
        if loc in self.events:
            n = self.events[loc][1]
            chain.event = [n.pitch.value.data, n.start.data, n.dur.data, n.vel.value.data]
        if loc in self.score_notes:
            n = self.score_notes[loc]
            chain.score = f"{n.pitch.data} at beat {n.beat.data} for {n.dur.data}, velocity {n.vel.value.data}"
        chain.override = self.overrides.notes.get(loc)
        section = self._section(name, occurrence)
        if section is None:
            return chain
        at = section.start.data + (bar - 1) * section.meter.data.beats_per_bar + beat
        part = next((p for p in self.voiced.parts() if p.part.data == track), None)
        for slot in part.slots() if part else []:
            if slot.section.data == tag and slot.start.data <= at < slot.start.data + slot.dur.data:
                chain.slot = next(
                    s for s in self.slots(tag, track) if s.target == loc_key(slot.location)
                )
                break
        for info in self.chords(name, occurrence):
            chord_at = section.start.data + _offset(info.position, section)
            if chord_at <= at:
                chain.chord = info
        return chain

    def clip(self, clip_id: str, note_ids: list[str] | None = None) -> ClipView | None:
        key = self.by_clip_id.get(clip_id)
        if key is None:
            return None
        tag, _, track = key.partition("/")
        name, _, occurrence = tag.partition("#")
        section = self._section(name, int(occurrence or 1))
        view = ClipView(
            key,
            tag,
            name,
            track,
            section.bars.value.data if section else 0,
            f"{section.key.data.root} {section.key.data.mode}" if section else "",
            f"{section.meter.data.numerator}/{section.meter.data.denominator}" if section else "",
        )
        view.chords = self.chords(name, int(occurrence or 1))
        view.track_info = self.track(name, track)
        view.slots = self.slots(tag, track)
        for note_id in note_ids or []:
            loc = self.by_note_id.get(note_id)
            chain = self.note(loc) if loc else None
            if chain is not None:
                view.notes.append(chain)
        return view


def _offset(where: str, section: score.SectionOp) -> Fraction:
    bar, _, beat = where.partition("+")
    return (int(bar) - 1) * section.meter.data.beats_per_bar + Fraction(beat)


def note_names(pitches: list[int], key: Key | None = None) -> str:
    return " ".join(spell(p, key or Key("C", "major")) for p in pitches)
