"""
puLang as tools an agent calls.

An agent cannot hear a song, but it can read one at every level, change it at
the level a change belongs to, propose alternatives for a person to hear and
pick, review the result, and render a window of it to measure. Each function
here does one of those to a song file and returns plain data, so the same
functions serve `pulang agent <tool> '<json>'` and `pulang mcp`, a Model Context
Protocol server.

    describe     the song in one read: form with bars and seconds, each section's
                 chart, every track's part, motifs, edits, variations
    ir           the IR at one stage, optionally one section
    edit / drop  change one thing above the notes, or forget a change
    propose      keep a named bundle of edits as an alternative at a site
    variations   the sites, their alternatives, and which is picked
    pick         choose an alternative at a site, or the source
    readings     what the hand edits in a clip might mean above the notes
    keep_reading keep one of those readings
    review       what the compiler's read-through finds, and each line's shape
    render       bounce a window to a WAV through kaiDAW and measure it
    audition     render every alternative at a site over the bars it changes

Every change is checked by compiling the song with it before it is kept; a
change the compiler refuses, or one aimed at a place that does not exist, is
reported and not saved.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from pypulang.backends.kaidaw.client import DEFAULT_PORT
from pypulang.backends.kaidaw.state import Overrides, SongState
from pypulang.compiler.dialects import event, intent
from pypulang.compiler.edits import LEVELS, Edit, current_value, section_chart, track_value
from pypulang.compiler.pipeline import CompileResult
from pypulang.songfile import Song, load_song
from pypulang.variations import SOURCE, Variation, effect, focus, sites, song_edits


class ToolError(ValueError):
    """A request the song cannot take, said in terms of the song."""


def _song(path: str | Path) -> tuple[Song, SongState, Overrides]:
    file = Path(path)
    if not file.exists():
        raise ToolError(f"No song at {file}")
    state = SongState.beside(file)
    return load_song(file), state, state.load_overrides()


def _top(module: Any, kind: type) -> Any:
    return next(o for o in module.body.block.ops if isinstance(o, kind))


def plain(value: Any) -> Any:
    """Data as JSON holds it: fractions become exact strings such as "1/4"."""
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def _clock(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


def _tempo(result: CompileResult) -> float:
    return float(_top(result.stages["intent"], intent.PieceOp).tempo.value.data)


# -- reading ---------------------------------------------------------------------------


def describe(song: str) -> dict[str, Any]:
    """
    The song in one read.

    Times assume the piece's one tempo. Bars count from 1 across the whole song.
    """
    loaded, _, overrides = _song(song)
    result = loaded.compile(until="event")
    piece = _top(result.stages["intent"], intent.PieceOp)
    stream = _top(result.stages["event"], event.StreamOp)
    tempo = float(piece.tempo.value.data)
    per_beat = 60.0 / tempo

    form = []
    bar = 1
    for marker in stream.sections():
        bars = int(marker.length.data / marker.meter.data.beats_per_bar)
        start = float(marker.at.data) * per_beat
        form.append(
            {
                "section": marker.tag.data,
                "bars": f"{bar}-{bar + bars - 1}",
                "time": f"{_clock(start)}-{_clock(start + float(marker.length.data) * per_beat)}",
            }
        )
        bar += bars

    sections = {}
    for section in piece.sections():
        tracks = {}
        for track in section.tracks():
            info: dict[str, Any] = {"role": track.role.data}
            melody = track_value(track, "melody")
            pattern = track_value(track, "pattern")
            notes = next((o for o in track.body.block.ops if isinstance(o, intent.NotesOp)), None)
            if melody is not None:
                info["melody"] = melody
            elif pattern is not None:
                info["pattern"] = pattern
            elif notes is not None:
                info["notes"] = len(list(notes.body.block.ops))
            for name in ("voicing", "octave", "velocity", "muted"):
                value = track_value(track, name)
                if value not in (None, 0, False) and not (name == "velocity" and value == 100):
                    info[name] = value
            tracks[track.track.data] = info
        key = section.key.data if section.key is not None else piece.key.data
        meter = section.meter.data if section.meter is not None else piece.meter.data
        sections[section.section.data] = {
            "bars": section.bars.value.data,
            "key": f"{key.root} {key.mode}",
            "meter": f"{meter.numerator}/{meter.denominator}",
            "chart": section_chart(section, piece),
            "tracks": tracks,
        }

    end = max((float(s.at.data + s.length.data) for s in stream.sections()), default=0.0)
    return plain(
        {
            "title": piece.title.data,
            "tempo": tempo,
            "key": f"{piece.key.data.root} {piece.key.data.mode}",
            "meter": f"{piece.meter.data.numerator}/{piece.meter.data.denominator}",
            "length": _clock(end * per_beat),
            "form": form,
            "motifs": piece.motifs(),
            "sections": sections,
            "pipeline": {
                stage: [repr(p) for p in passes] for stage, passes in loaded.pipeline.items()
            },
            "edits": [e.to_json() for e in overrides.edit_list()],
            "variations": _variations(overrides),
            "warnings": result.warnings,
        }
    )


def ir(song: str, stage: str = "intent", section: str | None = None) -> str:
    """
    The IR at one stage: intent, score, event or daw.

    With `section` at the intent stage, only that section; at later stages, only
    the lines located in its occurrences.
    """
    from pypulang.compiler import print_ir

    loaded, _, _ = _song(song)
    result = loaded.compile(until=stage)
    if stage not in result.stages:
        raise ToolError(f"No stage {stage!r}; stages are intent, score, event, daw")
    module = result.stages[stage]
    if section is None:
        return print_ir(module)
    if stage == "intent":
        piece = _top(module, intent.PieceOp)
        op = next((s for s in piece.sections() if s.section.data == section), None)
        if op is None:
            raise ToolError(f"No section {section!r}")
        return str(op)
    text = print_ir(module, locations=True)
    return "\n".join(line for line in text.splitlines() if f'"{section}#' in line)


def review(song: str) -> dict[str, Any]:
    """The compiler's read-through, and the shape of each melodic line."""
    from pypulang.compiler.check import review as read_through
    from pypulang.compiler.dialects import score
    from pypulang.compiler.locs import loc_key
    from pypulang.compiler.spelling import midi_of

    loaded, _, _ = _song(song)
    result = loaded.compile(until="score")
    found = read_through(result.stages["score"])
    by_kind: dict[str, list[dict[str, str]]] = {}
    for finding in found.findings:
        by_kind.setdefault(finding.kind, []).append(asdict(finding))
    top = _top(result.stages["score"], score.ScoreOp)
    lines = {}
    for part in top.parts():
        if part.role.data != "melody":
            continue
        per_section: dict[str, dict[str, Any]] = {}
        for bar in part.bars():
            for note in bar.notes():
                tag = loc_key(note.location).partition("/")[0]
                entry = per_section.setdefault(
                    tag, {"notes": 0, "low": 127, "high": 0, "beats": 0.0}
                )
                pitch = midi_of(note.pitch.data)
                entry["notes"] += 1
                entry["low"] = min(entry["low"], pitch)
                entry["high"] = max(entry["high"], pitch)
                entry["beats"] += float(note.dur.data)
        lines[part.part.data] = per_section
    return {
        "summary": found.summary().splitlines()[0],
        "findings": {
            kind: {"count": len(items), "first": items[:5]} for kind, items in by_kind.items()
        },
        "melodies": lines,
    }


def _variations(overrides: Overrides) -> dict[str, Any]:
    return plain(
        {
            site: {
                "picked": overrides.choices.get(site, SOURCE),
                "alternatives": [
                    {
                        "name": v.name,
                        "description": v.description,
                        "author": v.author,
                        "edits": [e.to_json() for e in v.edits],
                    }
                    for v in found
                ],
            }
            for site, found in sites(overrides).items()
        }
    )


def variations(song: str) -> dict[str, Any]:
    """Every site, its alternatives, and which is picked ("source" when none is)."""
    _, _, overrides = _song(song)
    return _variations(overrides)


# -- changing ---------------------------------------------------------------------------


def _typed(loaded: Song, edit: Edit, value: Any) -> Any:
    """A value as the edit carries it: text is read the way the companion page reads it."""
    if not isinstance(value, str):
        return value
    from pypulang.inspector import Model
    from pypulang.serve import Companion

    state = SongState.beside(loaded.path)
    model = Model(loaded.compile(keep_trace=True), state.load_lock(), state.load_overrides())
    try:
        return Companion._parse(model, edit, value)
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        raise ToolError(f"{edit.key}: cannot read {value!r}: {error}") from error


def _base(loaded: Song, edit: Edit, edits: list[Edit]) -> Any:
    """What the song gives at an edit's target now, with the other edits applied."""
    if edit.level == "intent":
        result = loaded.compile(until="intent", edits=edits)
        exists, value = current_value(result.stages["intent"], edit)
        if not exists:
            raise ToolError(f"{edit.key}: the song has no such place")
        return value
    from pypulang.inspector import Model
    from pypulang.serve import Companion

    state = SongState.beside(loaded.path)
    model = Model(
        loaded.compile(keep_trace=True, edits=edits), state.load_lock(), state.load_overrides()
    )
    return Companion._base(model, edit)


def _new_warnings(before: CompileResult, after: CompileResult) -> list[str]:
    """Warnings a change brought, telling counts apart from kinds."""

    def kind(line: str) -> str:
        return re.sub(r"\d+", "#", line)

    seen = {kind(w) for w in before.warnings}
    return [w for w in after.warnings if kind(w) not in seen]


def _checked(loaded: Song, edits: list[Edit], new: list[Edit]) -> CompileResult:
    """Compile with the edits; refuse ones the compiler rejects or that land nowhere."""
    try:
        result = loaded.compile(edits=edits)
    except (ValueError, KeyError) as error:
        raise ToolError(f"The song does not compile with this change: {error}") from error
    keys = {e.key for e in new}
    lost = [line for line in result.edits.orphaned if line.split(": ")[0] in keys]
    if lost:
        raise ToolError("; ".join(lost))
    return result


def _make(loaded: Song, spec: dict[str, Any], context: list[Edit]) -> Edit:
    """
    An edit from {"level", "target", "field", "value"}, its base read from the song
    with the `context` edits applied, except any earlier edit of the same thing:
    the base is what the song itself gives there.
    """
    level = spec.get("level", "intent")
    if level not in LEVELS:
        raise ToolError(f"No level {level!r}; levels are {', '.join(LEVELS)}")
    missing = [k for k in ("target", "field", "value") if k not in spec]
    if missing:
        raise ToolError(f"An edit needs {', '.join(missing)}")
    edit = Edit(level, spec["target"], spec["field"], None)
    edit.value = _typed(loaded, edit, spec["value"])
    edit.base = _base(loaded, edit, [e for e in context if e.key != edit.key])
    return edit


def edit(song: str, target: str, field: str, value: Any, level: str = "intent") -> dict[str, Any]:
    """
    Change one thing above the notes and keep the change beside the song.

    Targets name places by musical position, as `pypulang.compiler.edits` lists:
    "verse/harmony" chart, "verse/harmony@3+0" chord, "verse/keys" voicing |
    octave | velocity | muted | pattern | melody, "motif/hook" notes,
    "verse#2/harmony@3+0" chord at the score level, "verse#2/keys/c4" pitches.
    """
    loaded, state, overrides = _song(song)
    before = loaded.compile(edits=song_edits(overrides))
    change = _make(
        loaded,
        {"level": level, "target": target, "field": field, "value": value},
        song_edits(overrides),
    )
    if change.value == change.base:
        overrides.drop_edit(change.key)
        state.save_overrides(overrides)
        return {"edit": change.key, "result": "back to what the song gives"}
    trial = Overrides(**{**overrides.__dict__, "edits": list(overrides.edits)})
    trial.put_edit(change)
    after = _checked(loaded, song_edits(trial), [change])
    state.save_overrides(trial)
    return {
        "edit": change.key,
        "from": change.base,
        "to": change.value,
        "effect": effect(before, after).to_json(),
        "warnings": _new_warnings(before, after),
    }


def drop(song: str, key: str) -> dict[str, Any]:
    """Forget an edit, named "level:target:field" as `describe` lists it."""
    _, state, overrides = _song(song)
    if not overrides.drop_edit(key):
        raise ToolError(f"No edit {key}")
    state.save_overrides(overrides)
    return {"dropped": key}


def propose(
    song: str,
    site: str,
    name: str,
    edits: list[dict[str, Any]],
    description: str = "",
    author: str = "agent",
) -> dict[str, Any]:
    """
    Keep an alternative at a site: a named bundle of edits, not yet picked.

    Each edit is {"target", "field", "value"} and optionally "level" (default
    intent). The bundle is checked by compiling the song with it in place of
    whatever is picked at the site, and is described by the notes it changes.
    """
    loaded, state, overrides = _song(song)
    if not edits:
        raise ToolError("A variation needs at least one edit")
    if name == SOURCE:
        raise ToolError(f"{SOURCE!r} is the song's own version; choose another name")
    made = [_make(loaded, spec, song_edits(overrides, site=site)) for spec in edits]
    variation = Variation(name, site, made, description, author)
    source = loaded.compile(edits=song_edits(overrides, site=site))
    trial = _checked(loaded, song_edits(overrides, trying=variation), made)
    change = effect(source, trial)
    if not change.total:
        raise ToolError(f"{name} changes no notes against the source at {site!r}")
    overrides.put_variation(variation)
    state.save_overrides(overrides)
    return {
        "variation": name,
        "site": site,
        "effect": change.to_json(),
        "warnings": _new_warnings(source, trial),
    }


def pick(song: str, site: str, name: str) -> dict[str, Any]:
    """Choose an alternative at a site; "source" goes back to the song's own."""
    _, state, overrides = _song(song)
    try:
        overrides.pick(site, name)
    except (KeyError, ValueError) as error:
        raise ToolError(str(error)) from error
    state.save_overrides(overrides)
    return {"site": site, "picked": name}


def drop_variation(song: str, name: str) -> dict[str, Any]:
    """Forget a proposed variation; if it was picked, its site goes back to the source."""
    _, state, overrides = _song(song)
    if not overrides.drop_variation(name):
        raise ToolError(f"No variation {name}")
    state.save_overrides(overrides)
    return {"dropped": name}


def _readings(loaded: Song, state: SongState, clip: str) -> list[Any]:
    from pypulang import lift
    from pypulang.inspector import Model

    model = Model(loaded.compile(keep_trace=True), state.load_lock(), state.load_overrides())
    return lift.suggest(loaded, model, clip)


def readings(
    song: str, clip: str, port: int = DEFAULT_PORT, pull_first: bool = True
) -> dict[str, Any]:
    """
    What the hand edits in one clip, such as "chorus#1/trumpet", might mean above
    the notes: a chord, a voicing, an octave, a motif rewritten, a phrase moved.
    Each reading was checked by lowering; `explains` counts the hand edits it
    reproduces and `disturbs` the notes nobody touched that it would also change.
    """
    loaded, state, _ = _song(song)
    if pull_first:
        from pypulang.backends.kaidaw import KaidawClient, pull

        pull(KaidawClient(port=port), state)
    found = _readings(loaded, state, clip)
    edited = sum(1 for loc in state.load_overrides().notes if loc.startswith(clip + "/"))
    return plain(
        {
            "clip": clip,
            "hand_edits": edited,
            "readings": [
                {
                    "index": index,
                    "reason": s.reason,
                    "edits": [e.to_json() for e in s.edits],
                    "explains": len(s.explains),
                    "disturbs": s.disturbs,
                }
                for index, s in enumerate(found)
            ],
        }
    )


def keep_reading(song: str, clip: str, index: int) -> dict[str, Any]:
    """Keep reading `index` of a clip's hand edits: its edits stay, the note edits it explains go."""
    from pypulang import lift

    loaded, state, _ = _song(song)
    found = _readings(loaded, state, clip)
    if not 0 <= index < len(found):
        raise ToolError(f"{clip} has {len(found)} reading(s)")
    chosen = found[index]
    state.save_overrides(lift.accept(loaded, state.load_overrides(), chosen))
    return plain(
        {"kept": [e.to_json() for e in chosen.edits], "dropped_note_edits": len(chosen.explains)}
    )


# -- hearing, by measurement --------------------------------------------------------------


def _levels(path: Path) -> dict[str, float]:
    import numpy as np
    import soundfile as sf

    audio, _ = sf.read(path, always_2d=True)

    def db(x: float) -> float:
        return round(20 * float(np.log10(max(x, 1e-9))), 1)

    return {
        "rms_db": db(float(np.sqrt(np.mean(audio**2)))),
        "peak_db": db(float(np.abs(audio).max())),
    }


def _bounce(
    loaded: Song, edits: list[Edit], out: Path, start: float, seconds: float, port: int
) -> dict[str, Any]:
    from pypulang.backends.kaidaw import KaidawClient, push
    from pypulang.cli import _render_to

    client = KaidawClient(port=port)
    push(loaded.compile(edits=edits).daw, client, SongState.beside(loaded.path))
    out.parent.mkdir(parents=True, exist_ok=True)
    rendered = _render_to(client, out, start, seconds)
    return {"file": str(out), "seconds": round(rendered["audioSeconds"], 2), **_levels(out)}


def _bar_starts(result: CompileResult) -> list[Fraction]:
    """The beat each bar starts on, bars counted from 1 across the song, then the end."""
    stream = _top(result.stages["event"], event.StreamOp)
    starts: list[Fraction] = []
    end = Fraction(0)
    for marker in stream.sections():
        per_bar = marker.meter.data.beats_per_bar
        at = marker.at.data
        while at < marker.at.data + marker.length.data:
            starts.append(at)
            at += per_bar
        end = max(end, marker.at.data + marker.length.data)
    return [*starts, end]


def render(
    song: str,
    out: str,
    section: str | None = None,
    start_bar: int | None = None,
    bars: int = 8,
    port: int = DEFAULT_PORT,
) -> dict[str, Any]:
    """
    Push the song to kaiDAW and bounce a window of it.

    Give a section occurrence such as "chorus#2", or a first bar and a number of
    bars, or neither for the whole song.
    """
    loaded, _, overrides = _song(song)
    edits = song_edits(overrides)
    result = loaded.compile(until="event", edits=edits)
    per_beat = 60.0 / _tempo(result)
    starts = _bar_starts(result)
    if section is not None:
        stream = _top(result.stages["event"], event.StreamOp)
        marker = next((s for s in stream.sections() if s.tag.data == section), None)
        if marker is None:
            tags = [s.tag.data for s in stream.sections()]
            raise ToolError(f"No section occurrence {section!r}; the form is {tags}")
        begin, end = marker.at.data, marker.at.data + marker.length.data
    elif start_bar is not None:
        if not 1 <= start_bar < len(starts):
            raise ToolError(f"Bars run from 1 to {len(starts) - 1}")
        begin = starts[start_bar - 1]
        end = starts[min(start_bar - 1 + bars, len(starts) - 1)]
    else:
        begin, end = Fraction(0), starts[-1] + Fraction(4)
    return _bounce(
        loaded, edits, Path(out), float(begin) * per_beat, float(end - begin) * per_beat, port
    )


def audition(
    song: str, site: str, out_dir: str, section: str | None = None, port: int = DEFAULT_PORT
) -> dict[str, Any]:
    """
    Render the source and every alternative at a site over the same window, with a
    bar before it: `section` if given, such as "chorus#1", else the first section
    occurrence where the alternatives change at least half as many notes as where
    they change most. The song is pushed back as picked afterwards.
    """
    loaded, _, overrides = _song(song)
    found = sites(overrides).get(site)
    if not found:
        raise ToolError(f"No variations at {site!r}")
    source = loaded.compile(edits=song_edits(overrides, site=site))
    tempo = _tempo(source)
    effects = {
        v.name: effect(source, loaded.compile(edits=song_edits(overrides, trying=v))) for v in found
    }
    stream = _top(source.stages["event"], event.StreamOp)
    order = [s.tag.data for s in stream.sections()]
    tag = section or focus(list(effects.values()), order)
    if tag is None:
        raise ToolError(f"No variation at {site!r} changes any notes")
    occurrence = next((s for s in stream.sections() if s.tag.data == tag), None)
    if occurrence is None:
        raise ToolError(f"No section occurrence {tag!r}; the form is {order}")
    bar = float(occurrence.meter.data.beats_per_bar)
    begin = max(0.0, float(occurrence.at.data) - bar)
    end = float(occurrence.at.data + occurrence.length.data)
    start, seconds = begin * 60.0 / tempo, (end - begin) * 60.0 / tempo + 1.0
    out = Path(out_dir)
    renders = {
        SOURCE: _bounce(
            loaded, song_edits(overrides, site=site), out / f"{SOURCE}.wav", start, seconds, port
        )
    }
    try:
        for variation in found:
            renders[variation.name] = {
                **_bounce(
                    loaded,
                    song_edits(overrides, trying=variation),
                    out / f"{variation.name}.wav",
                    start,
                    seconds,
                    port,
                ),
                "effect": effects[variation.name].summary(),
                "description": variation.description,
            }
    finally:
        from pypulang.backends.kaidaw import KaidawClient, push

        push(
            loaded.compile(edits=song_edits(overrides)).daw,
            KaidawClient(port=port),
            SongState.beside(loaded.path),
        )
    return {
        "site": site,
        "window": f"{_clock(start)}-{_clock(start + seconds)} ({occurrence.tag.data})",
        "picked": overrides.choices.get(site, SOURCE),
        "renders": renders,
    }


# -- the table the CLI and the MCP server share ---------------------------------------------

TOOLS: dict[str, Any] = {
    "describe": describe,
    "ir": ir,
    "review": review,
    "variations": variations,
    "edit": edit,
    "drop": drop,
    "propose": propose,
    "pick": pick,
    "drop_variation": drop_variation,
    "readings": readings,
    "keep_reading": keep_reading,
    "render": render,
    "audition": audition,
}
