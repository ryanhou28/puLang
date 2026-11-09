"""
Lifting: reading hand edits made in the DAW as edits at a higher level.

Moving three notes of a chord in the piano roll is recorded as three note edits.
Often it means something higher: a different voicing of that chord, a different
chord, the part an octave up. This module proposes such readings and checks each
the only way that is honest, by lowering it: the song is recompiled with the
proposed edit, and the proposal counts the hand edits it reproduces exactly and the
notes nobody touched that it would also change.

Accepting a proposal keeps the higher edit and drops the note edits it explains.
Note edits it does not explain stay, rebased onto what the source now gives.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from xdsl.dialects.builtin import ModuleOp

from pypulang.backends.kaidaw.state import Overrides
from pypulang.compiler.dialects import daw
from pypulang.compiler.edits import Edit
from pypulang.compiler.locs import loc_key
from pypulang.harmony import chord_symbol, parse_chord_symbol, root_pitch_class
from pypulang.inspector import Model, parse_loc
from pypulang.ir.intent import Key
from pypulang.resolution import resolve_chord
from pypulang.songfile import Song

# Chord qualities tried when edited notes spell a chord, as chart suffixes.
QUALITIES = (
    "",
    "m",
    "7",
    "maj7",
    "m7",
    "m7b5",
    "dim7",
    "6",
    "m6",
    "9",
    "maj9",
    "m9",
    "7sus4",
    "sus4",
    "13",
    "7b9",
    "7#9",
)
ROOTS = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")


@dataclass
class Suggestion:
    """One reading of some hand edits: one or more edits above the notes."""

    edits: list[Edit]
    reason: str
    explains: list[str] = field(default_factory=list)
    in_scope: int = 0
    disturbs: int = 0

    @property
    def id(self) -> str:
        return " & ".join(f"{e.key}={e.value!r}" for e in self.edits)


def daw_notes(module: ModuleOp) -> dict[str, list[int]]:
    """Every generated note in a project, by location."""
    project = next(o for o in module.body.block.ops if isinstance(o, daw.ProjectOp))
    return {
        loc_key(n.location): list(n.as_tuple())
        for t in project.tracks()
        for c in t.clips()
        for n in c.notes()
    }


def _scope(overrides: Overrides, clip_key: str | None) -> dict[str, dict[str, Any]]:
    return {
        loc: entry
        for loc, entry in overrides.notes.items()
        if clip_key is None or loc.startswith(clip_key + "/")
    }


def _voice(loc: str) -> int | None:
    parsed = parse_loc(loc)
    if parsed is None or not parsed[5].startswith("v"):
        return None
    return int(parsed[5][1:])


def candidates(model: Model, clip_key: str | None) -> list[Suggestion]:
    """Proposals worth checking, before any is lowered."""
    edits = _scope(model.overrides, clip_key)
    out: list[Suggestion] = []
    by_slot: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    by_part: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for loc, entry in edits.items():
        chain = model.note(loc)
        if chain is None:
            continue
        if chain.slot is not None:
            by_slot[chain.slot.target].append((loc, entry))
        by_part[(chain.section, chain.track)].append((loc, entry))

    for target, items in by_slot.items():
        chain = model.note(items[0][0])
        slot = chain.slot
        voices = dict(enumerate(slot.pitches))
        heard: dict[int, set[int]] = defaultdict(set)
        removed: set[int] = set()
        for loc, entry in items:
            voice = _voice(loc)
            if voice is None:
                continue
            if entry.get("deleted"):
                removed.add(voice)
            else:
                heard[voice].add(entry["note"][0])
        changed = False
        for voice, pitches in heard.items():
            if len(pitches) == 1:
                voices[voice] = next(iter(pitches))
                changed = True
        for voice in removed - set(heard):
            voices.pop(voice, None)
            changed = True
        if not changed:
            continue
        actual = sorted(voices.values())
        pre_octave = [p - 12 * slot.octave for p in actual]
        voicing = Edit(
            "score", target, "pitches", pre_octave, [p - 12 * slot.octave for p in slot.pitches]
        )
        out.append(Suggestion([voicing], f"a new voicing of {slot.chord} in {chain.tag}"))
        key = _key(model, chain.section)
        spelled = {p % 12 for p in actual}
        # A different chord. Paired with the voicing as played, because a new chord is
        # voiced afresh and would not reproduce the notes; the pair keeps the notes and
        # tells every other part what the harmony now is. The voicing's base is filled
        # in by `check`, as what the new chord voices to.
        for name in _chords_spelling(spelled, key)[:2]:
            if name == slot.chord or chain.chord is None:
                continue
            keep = Edit("score", target, "pitches", pre_octave, None)
            out.append(
                Suggestion(
                    [
                        Edit(
                            "score",
                            chain.chord.score_target(chain.tag),
                            "chord",
                            name,
                            chain.chord.symbol,
                        ),
                        keep,
                    ],
                    f"the notes spell {name}, not {slot.chord}: change the chord in {chain.tag}, "
                    "keeping these notes",
                )
            )
            if chain.chord.written is not None:
                out.append(
                    Suggestion(
                        [
                            Edit(
                                "intent",
                                chain.chord.intent_target(chain.section),
                                "chord",
                                name,
                                chain.chord.written,
                            ),
                            Edit("score", target, "pitches", list(pre_octave), None),
                        ],
                        f"the notes spell {name}: change it in every {chain.section}, keeping these notes "
                        f"in {chain.tag}",
                    )
                )

    for (section, track), items in by_part.items():
        info = model.track(section, track)
        if info is None:
            continue
        moved = [e for _, e in items if not e.get("deleted")]
        if moved and len(moved) == len(items):
            shifts = {e["note"][0] - e["base"][0] for e in moved}
            if len(shifts) == 1 and next(iter(shifts)) % 12 == 0 and next(iter(shifts)):
                octaves = next(iter(shifts)) // 12
                out.append(
                    Suggestion(
                        [
                            Edit(
                                "intent",
                                info.target,
                                "octave",
                                info.settings["octave"] + octaves,
                                info.settings["octave"],
                            )
                        ],
                        f"every edited {track} note moved {octaves:+d} octave(s); in every {section}",
                    )
                )
            deltas = {e["note"][3] - e["base"][3] for e in moved}
            same_pitch = all(e["note"][:3] == e["base"][:3] for e in moved)
            if same_pitch and len(deltas) == 1 and next(iter(deltas)):
                delta = next(iter(deltas))
                out.append(
                    Suggestion(
                        [
                            Edit(
                                "intent",
                                info.target,
                                "velocity",
                                max(1, min(127, info.settings["velocity"] + delta)),
                                info.settings["velocity"],
                            )
                        ],
                        f"every edited {track} note is {delta:+d} louder; in every {section}",
                    )
                )
        if items and all(e.get("deleted") for _, e in items) and not info.settings["muted"]:
            out.append(
                Suggestion(
                    [Edit("intent", info.target, "muted", True, False)],
                    f"{track} notes were deleted; mute it in every {section}",
                )
            )
    return out


def _key(model: Model, section: str) -> Key:
    op = model._intent_section(section)  # noqa: SLF001 — the model's own index
    return op.key.data if op is not None and op.key is not None else model.intent.key.data


def _chords_spelling(pitch_classes: set[int], key: Key) -> list[str]:
    """Chord symbols whose notes are these, or these less the root (a rootless voicing)."""
    if len(pitch_classes) < 3:
        return []
    found = []
    for root in ROOTS:
        for quality in QUALITIES:
            name = root + quality
            try:
                chord = parse_chord_symbol(name, key)
            except ValueError:
                continue
            notes = {p % 12 for p in resolve_chord(chord, key)}
            root_pc = root_pitch_class(chord, key)
            if pitch_classes == notes or pitch_classes == notes - {root_pc}:
                found.append(chord_symbol(chord, key))
    return found


def check(song: Song, model: Model, suggestion: Suggestion, clip_key: str | None) -> Suggestion:
    """Lower the song with the proposal and count what it reproduces and disturbs."""
    scope = _scope(model.overrides, clip_key)
    keys = {e.key for e in suggestion.edits}
    existing = [e for e in model.overrides.edit_list() if e.key not in keys]
    unknown = [e for e in suggestion.edits if e.base is None and e.field == "pitches"]
    if unknown:
        # What the slot voices to once the rest of the proposal is in, so the kept
        # voicing is stale only if the source later moves under it.
        others = [e for e in suggestion.edits if e not in unknown]
        voiced = song.compile(until="score", keep_trace=True, edits=[*existing, *others])
        from pypulang.compiler.edits import score_slot
        from pypulang.inspector import voiced_module

        top = next(o for o in voiced_module(voiced).body.block.ops if o.name == "score.score")
        for edit in unknown:
            slot = score_slot(top, edit.target)
            edit.base = slot.pitch_list() if slot is not None else None
    before = _heard(daw_notes(model.result.stages["daw"]))
    after = _heard(daw_notes(song.compile(edits=[*existing, *suggestion.edits]).daw))
    suggestion.in_scope = len(scope)
    # Notes are compared by clip, time and pitch, not by location: voices are
    # numbered low to high, so a voicing that puts a note on top renumbers the
    # voices under it while every note sounds where it was put.
    suggestion.explains = [
        loc
        for loc, entry in scope.items()
        if (
            after[(_clip(loc), tuple(entry["base"]))] < before[(_clip(loc), tuple(entry["base"]))]
            if entry.get("deleted")
            else after[(_clip(loc), tuple(entry["note"]))] > 0
        )
    ]
    edited_to = Counter(
        (_clip(loc), tuple(e["note"]))
        for loc, e in model.overrides.notes.items()
        if not e.get("deleted")
    )
    edited_from = Counter(
        (_clip(loc), tuple(e["base"])) for loc, e in model.overrides.notes.items()
    )
    # A note that moves is one removed and one added; count it once.
    suggestion.disturbs = max(
        sum(((after - before) - edited_to).values()), sum(((before - after) - edited_from).values())
    )
    return suggestion


def _clip(loc: str) -> str:
    return "/".join(loc.split("/")[:2])


def _heard(notes: dict[str, list[int]]) -> Counter[tuple[str, tuple[int, ...]]]:
    return Counter((_clip(loc), tuple(note)) for loc, note in notes.items())


def suggest(song: Song, model: Model, clip_key: str | None) -> list[Suggestion]:
    """Checked proposals that explain at least one hand edit, best first."""
    seen: set[str] = set()
    result = []
    for suggestion in candidates(model, clip_key):
        if suggestion.id in seen:
            continue
        seen.add(suggestion.id)
        check(song, model, suggestion, clip_key)
        if suggestion.explains:
            result.append(suggestion)
    result.sort(key=lambda s: (-len(s.explains), s.disturbs))
    return result


def accept(song: Song, overrides: Overrides, suggestion: Suggestion) -> Overrides:
    """Keep the higher edits; drop the note edits they explain; rebase the rest."""
    for edit in suggestion.edits:
        overrides.put_edit(edit)
    after = daw_notes(song.compile(edits=overrides.edit_list()).daw)
    for loc in suggestion.explains:
        overrides.notes.pop(loc, None)
    for loc, entry in overrides.notes.items():
        if loc in after:
            entry["base"] = after[loc]
    return overrides
