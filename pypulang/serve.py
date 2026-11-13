"""
`pulang serve`: the song's IR beside kaiDAW, and edits at every level.

kaiDAW shows this page in its source panel, passing the selected clip and notes.
It has three views. The song: every section's chart, tempo and parts, the motifs
and the mix, each an input, with the line of the song that set it. The
selection: what produced the selected notes, level by level, with the edits each
level can take, and the hand edits made in kaiDAW read as the higher edits they
might mean. The changes: the edits kept beside the song, the variations to
pick from, and folding the edits into the song's source.

An edit is kept in the song's overrides at the level it was made, then the song is
recompiled and pushed, so kaiDAW shows the result a moment later. Nothing here is
part of kaiDAW's protocol: kaiDAW passes ids and shows a page, and the music stays
on this side (kaiDAW blueprint §3.10).
"""

from __future__ import annotations

import html
import json
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from pypulang import lift
from pypulang.backends.kaidaw import KaidawClient, KaidawError, SongState, pull, push
from pypulang.compiler.edits import Edit, current_value, plain
from pypulang.compiler.passes.voice_lead import parse_spec
from pypulang.compiler.spelling import midi_of, spell
from pypulang.context_patterns import CONTEXT_PATTERNS
from pypulang.harmony import parse_chart, parse_chord_symbol
from pypulang.inspector import ClipView, Model, NoteChain
from pypulang.ir.intent import Key
from pypulang.motifs import parse_motif, parse_phrase
from pypulang.panel import Lines, fold_html, song_html
from pypulang.patterns import PATTERN_REGISTRY
from pypulang.songfile import load_song
from pypulang.variations import SOURCE, sites

DEFAULT_LISTEN = 8950


class Companion:
    """One song, compiled on demand, and the edits made through the page."""

    def __init__(self, song_path: str | Path, client: KaidawClient | None):
        self.path = Path(song_path)
        self.state = SongState.beside(self.path)
        self.client = client
        self.guard = threading.RLock()
        self.message = ""
        self._stamp: tuple[float, ...] | None = None
        self._model: Model | None = None
        self._lines: Lines | None = None
        self._title = ""
        self.suggestions: dict[str, list[lift.Suggestion]] = {}
        # Readings and the fold preview are slow, so each is kept until the files change
        self._read_at: dict[str, tuple[float, ...]] = {}
        self._folding: tuple[tuple[float, ...], str] | None = None

    def _files_stamp(self) -> tuple[float, ...]:
        files = [
            self.path,
            self.state.directory / "overrides.json",
            self.state.directory / "lock.json",
        ]
        return tuple(f.stat().st_mtime if f.exists() else 0.0 for f in files)

    def model(self) -> Model:
        with self.guard:
            stamp = self._files_stamp()
            if self._model is None or stamp != self._stamp:
                song = load_song(self.path)
                result = song.compile(keep_trace=True)
                self._title = self.path.stem
                self._model = Model(result, self.state.load_lock(), self.state.load_overrides())
                self._lines = Lines(song.builder, self.path)
                self._stamp = stamp
            return self._model

    # -- edits --------------------------------------------------------------------------

    def edit(self, level: str, target: str, field: str, text: str) -> str:
        with self.guard:
            model = self.model()
            overrides = self.state.load_overrides()
            edit = Edit(level, target, field, None)
            edit.value = self._parse(model, edit, text)
            existing = {e.key: e for e in overrides.edit_list()}
            if edit.key in existing:
                edit.base = existing[edit.key].base
            else:
                edit.base = self._base(model, edit)
            if edit.value == edit.base:
                overrides.drop_edit(edit.key)
                note = f"{edit.key} is back to what the source says"
            else:
                overrides.put_edit(edit)
                note = f"{edit.key}: {edit.base!r} -> {edit.value!r}"
            self.state.save_overrides(overrides)
            return note + self.push()

    def pick(self, site: str, name: str) -> str:
        with self.guard:
            overrides = self.state.load_overrides()
            overrides.pick(site, name)
            self.state.save_overrides(overrides)
            return f"{site}: {name}" + self.push()

    def drop(self, key: str) -> str:
        with self.guard:
            overrides = self.state.load_overrides()
            if not overrides.drop_edit(key):
                return f"no edit {key}"
            self.state.save_overrides(overrides)
            return f"dropped {key}" + self.push()

    def readings(self, clip_key: str, back: str) -> str:
        """
        Capture the hand edits made in kaiDAW, then read the selected clip's as the
        higher edits they might mean: what the selection view shows as soon as a
        clip with hand edits is selected.
        """
        with self.guard:
            if self.client is not None:
                try:
                    pull(self.client, self.state)
                except KaidawError as error:
                    return f'<p class="dim">Could not read kaiDAW: {_e(error)}</p>'
            model = self.model()
            view = model.clip(model.lock.clips.get(clip_key, {}).get("id", ""))
            edited = [loc for loc in model.overrides.notes if loc.startswith(clip_key + "/")]
            if view is None or not edited:
                return (
                    '<p class="dim">No hand edits in this clip. Notes moved, drawn or deleted '
                    "in kaiDAW are read here when the clip is selected.</p>"
                )
            if self._read_at.get(clip_key) != self._stamp:
                self.suggestions[clip_key] = lift.suggest(load_song(self.path), model, clip_key)
                self._read_at[clip_key] = self._stamp
            return "\n".join(_lift_html(view, model, self.suggestions[clip_key], back))

    def fold_preview(self, back: str) -> str:
        """What folding would write, computed once per change of the song's files."""
        from pypulang.fold import fold

        stamp = self._files_stamp()
        if self._folding is None or self._folding[0] != stamp:
            try:
                result = fold(self.path, write=False)
            except ValueError as error:
                return f'<p class="dim">{_e(error)}</p>'
            self._folding = (stamp, fold_html(result, self.path.name, back))
        return self._folding[1]

    def fold(self) -> str:
        from pypulang.fold import fold

        with self.guard:
            result = fold(self.path)
            self._stamp = None
            note = f"Wrote {len(result.folded)} edit(s) into {self.path.name}"
            if result.kept:
                note += f"; {len(result.kept)} stay beside it"
            return note + self.push()

    def accept(self, clip_key: str, index: int) -> str:
        with self.guard:
            suggestion = self.suggestions.get(clip_key, [])[index]
            overrides = lift.accept(load_song(self.path), self.state.load_overrides(), suggestion)
            self.state.save_overrides(overrides)
            self.suggestions.pop(clip_key, None)
            self._read_at.pop(clip_key, None)
            return f"kept {suggestion.id}" + self.push()

    def push(self) -> str:
        """Recompile and send the difference to kaiDAW, if there is one."""
        if self.client is None:
            return " (no kaiDAW connected: run with --port to push)"
        song = load_song(self.path)
        result = song.compile()
        try:
            report = push(result.daw, self.client, self.state)
        except KaidawError as error:
            return f" — push failed: {error}"
        self._stamp = None
        return f" — pushed: {report.summary().splitlines()[0]}"

    @staticmethod
    def _parse(model: Model, edit: Edit, text: str) -> Any:
        text = text.strip()
        if edit.field == "chord":
            parse_chord_symbol(text, Key("C", "major"))  # the symbol must read; its key comes later
            return text
        if edit.field == "voicing":
            if text:
                parse_spec(text)
            return text or None
        if edit.field in ("octave", "velocity"):
            return int(text)
        if edit.field == "muted":
            return text.lower() in ("1", "on", "true", "yes")
        if edit.field == "melody":
            parse_phrase(text)
            return text
        if edit.field in ("tempo", "volume", "pan"):
            return float(text) if text else None
        if edit.field == "chart":
            parse_chart(text, Key("C", "major"))  # the symbols must read; the key comes later
            return text
        if edit.field == "notes":
            parse_motif(text)
            return text
        if edit.field == "pattern":
            kind, _, params = text.partition(" ")
            if kind not in PATTERN_REGISTRY and kind not in CONTEXT_PATTERNS:
                raise ValueError(f"no pattern {kind!r}")
            return {"kind": kind, "params": json.loads(params) if params.strip() else {}}
        if edit.field == "pitches":
            slot = next(
                (s for t in model.voiced.parts() for s in t.slots() if _slot_key(s) == edit.target),
                None,
            )
            octave = slot.octave.value.data if slot is not None else 0
            names = text.replace(",", " ").split()
            return [(int(n) if n.isdigit() else midi_of(n)) - 12 * octave for n in names]
        raise ValueError(f"cannot edit {edit.field!r}")

    @staticmethod
    def _base(model: Model, edit: Edit) -> Any:
        if edit.level == "intent":
            return current_value(model.result.stages["intent"], edit)[1]
        if edit.field == "chord":
            name, _, rest = edit.target.partition("/")
            section, _, occurrence = name.partition("#")
            where = rest.removeprefix("harmony@")
            return next(
                (c.symbol for c in model.chords(section, int(occurrence)) if c.position == where),
                None,
            )
        slot = next(
            (s for t in model.voiced.parts() for s in t.slots() if _slot_key(s) == edit.target),
            None,
        )
        return slot.pitch_list() if slot is not None else None

    # -- the page -----------------------------------------------------------------------

    def page(self, query: dict[str, str]) -> str:
        model = self.model()
        clip_id = query.get("clipId", "")
        note_ids = [n for n in query.get("noteIds", "").split(",") if n]
        if not clip_id and note_ids:
            loc = model.by_note_id.get(note_ids[0], "")
            entry = model.lock.notes.get(loc)
            clip_id = model.lock.clips.get(entry["clip"], {}).get("id", "") if entry else ""
        view = model.clip(clip_id, note_ids) if clip_id else None
        back = "/inspect?" + urlencode({"clipId": clip_id, "noteIds": ",".join(note_ids)})
        edits = model.overrides.edit_list()
        tabs = {
            "song": (
                "song",
                song_html(model, self._lines, back, view and (view.section, view.track)),
            ),
            "selection": ("selection", self._selection(view, clip_id, model, back)),
            "changes": (
                f"changes ({len(edits)})" if edits else "changes",
                [
                    *_edits_html(model, back),
                    "<h2>Fold into the source</h2>",
                    f'<div data-fragment="/fragment/fold?{urlencode({"back": back})}">'
                    '<p class="dim">Checking what can be written into the source…</p></div>',
                    *_variations_html(model, back),
                ],
            ),
        }
        body = [
            f"<header><h1>{_e(self._title)}</h1><nav>"
            + "".join(
                f'<a href="#" data-tab="{k}">{_e(label)}</a>' for k, (label, _) in tabs.items()
            )
            + "</nav></header>"
        ]
        # Kept until the next action: kaiDAW reloads this page when the push it
        # caused lands, and a message cleared on first view would flash and vanish.
        if self.message:
            body.append(f'<p class="msg">{_e(self.message)}</p>')
        for name, (_, content) in tabs.items():
            body.append(
                f'<section class="tab" id="tab-{name}" hidden>' + "\n".join(content) + "</section>"
            )
        return _PAGE.replace("{body}", "\n".join(body))

    @staticmethod
    def _selection(view: ClipView | None, clip_id: str, model: Model, back: str) -> list[str]:
        if view is None:
            return [
                '<p class="dim">Select a clip in kaiDAW, or notes in its piano roll, to see '
                "what produced them.</p>"
                if not clip_id
                else f'<p class="dim">Clip {_e(clip_id)} did not come from this song.</p>'
            ]
        return [
            *_clip_html(view, model, back),
            '<h2>Hand edits in this clip <span class="lvl">daw → higher</span></h2>',
            f'<div data-fragment="/fragment/readings?{urlencode({"clip": view.key, "back": back})}">'
            '<p class="dim">Reading the edits made in kaiDAW…</p></div>',
        ]


def _slot_key(slot: Any) -> str:
    from pypulang.compiler.locs import loc_key

    return loc_key(slot.location)


def _e(value: Any) -> str:
    return html.escape(str(value))


def _form(level: str, target: str, field: str, value: Any, back: str, width: int = 10) -> str:
    shown = "" if value is None else value
    if isinstance(shown, bool):
        shown = "on" if shown else "off"
    return (
        f'<form method="post" action="/edit" class="inline">'
        f'<input type="hidden" name="level" value="{_e(level)}">'
        f'<input type="hidden" name="target" value="{_e(target)}">'
        f'<input type="hidden" name="field" value="{_e(field)}">'
        f'<input type="hidden" name="back" value="{_e(back)}">'
        f'<input name="value" value="{_e(shown)}" size="{width}" title="Enter to apply">'
        f"</form>"
    )


def _note_row(chain: NoteChain, key: Key) -> str:
    daw = chain.daw
    daw_text = f"{spell(daw[0], key)} @ {daw[1]} for {daw[2]}, vel {daw[3]}" if daw else "—"
    event_text = (
        f"{spell(chain.event[0], key)} @ beat {chain.event[1]} for {chain.event[2]}, vel {chain.event[3]}"
        if chain.event
        else "—"
    )
    edited = ""
    if chain.override:
        edited = (
            '<span class="tag">deleted in the DAW</span>'
            if chain.override.get("deleted")
            else f'<span class="tag">moved in the DAW to {_e(chain.override["note"])}</span>'
        )
    return (
        f"<tr><td>{_e(chain.where)}</td><td>{_e(daw_text)}</td><td>{_e(event_text)}</td>"
        f"<td>{_e(chain.score or '—')}</td>"
        f"<td>{_e(chain.slot.target if chain.slot else '—')}</td>"
        f"<td>{_e(chain.chord.symbol if chain.chord else '—')}</td><td>{edited}</td></tr>"
    )


def _clip_html(view: ClipView, model: Model, back: str) -> list[str]:
    key = Key(*view.key_name.split(" ")) if view.key_name else Key("C", "major")
    out = [
        f'<p class="where"><b>{_e(view.tag)}</b> · {_e(view.track)} · {_e(view.key_name)} · '
        f"{_e(view.meter)} · {view.bars} bars</p>"
    ]
    if view.notes:
        out.append('<h2>Selected notes <span class="lvl">daw → event → score</span></h2>')
        out.append(
            "<table><tr><th>place</th><th>in kaiDAW (ticks)</th><th>event</th><th>score</th>"
            "<th>slot</th><th>chord</th><th></th></tr>"
        )
        out.extend(_note_row(n, key) for n in view.notes)
        out.append("</table>")

    wanted = {n.slot.target for n in view.notes if n.slot} or {s.target for s in view.slots}
    slots = [s for s in view.slots if s.target in wanted]
    if slots:
        out.append(
            f'<h2>Voicings <span class="lvl">score · {_e(view.tag)} only</span></h2>'
            '<p class="dim">The exact notes of a chord in this part. Every hit of the chord '
            "plays them.</p><table><tr><th>slot</th><th>chord</th><th>pattern</th><th>notes</th></tr>"
        )
        for slot in slots:
            out.append(
                f"<tr><td>{_e(slot.target)}</td><td>{_e(slot.chord)}</td><td>{_e(slot.kind)}</td>"
                f"<td>{_form('score', slot.target, 'pitches', ' '.join(spell(p, key) for p in slot.pitches), back, 24)}</td></tr>"
            )
        out.append("</table>")

    if view.chords:
        out.append(
            f'<h2>Chords <span class="lvl">score · {_e(view.tag)} only</span> and '
            f'<span class="lvl">intent · every {_e(view.section)}</span></h2>'
            "<table><tr><th>at</th><th>this time only</th><th>every time</th></tr>"
        )
        for chord in view.chords:
            out.append(
                f"<tr><td>{_e(chord.position)}</td>"
                f"<td>{_form('score', chord.score_target(view.tag), 'chord', chord.symbol, back)}</td>"
                f"<td>{_form('intent', chord.intent_target(view.section), 'chord', chord.written, back)}</td></tr>"
            )
        out.append("</table>")

    track = view.track_info
    if track is not None:
        out.append(
            f'<h2>The {_e(view.track)} part <span class="lvl">intent · every {_e(view.section)}</span></h2>'
            "<table>"
        )
        for name, value in track.settings.items():
            if name == "pattern":
                text = value["kind"] + (
                    " " + json.dumps(plain(value["params"])) if value["params"] else ""
                )
                hint = "a pattern name, optionally followed by its parameters as JSON"
            elif name == "melody":
                text, hint = (
                    value,
                    "motifs and how each is developed, such as: hook; hook +1; hook end 1",
                )
            else:
                text, hint = (
                    value,
                    {
                        "voicing": "rootless(52,72), drop2, close… or empty for none",
                        "octave": "octaves up or down",
                        "velocity": "1–127",
                        "muted": "on or off",
                    }[name],
                )
            out.append(
                f"<tr><td>{_e(name)}</td><td>{_form('intent', track.target, name, text, back, 28)}</td>"
                f'<td class="dim">{_e(hint)}</td></tr>'
            )
        out.append("</table>")
        if track.motifs:
            out.append(
                '<h2>Its motifs <span class="lvl">intent · everywhere each is used</span></h2>'
                "<table>"
            )
            for motif, notes in track.motifs.items():
                out.append(
                    f"<tr><td>{_e(motif)}</td><td>{_form('intent', f'motif/{motif}', 'notes', notes, back, 28)}</td>"
                    '<td class="dim">scale degrees and note values, such as 5/8 6 1\'/4 7/8</td></tr>'
                )
            out.append("</table>")
    return out


def _lift_html(
    view: ClipView, model: Model, found: list[lift.Suggestion] | None, back: str
) -> list[str]:
    edited = [loc for loc in model.overrides.notes if loc.startswith(view.key + "/")]
    out = [
        f'<p class="dim">{len(edited)} note edit(s) made in kaiDAW are kept here, each read '
        "as the higher edits it might mean; every reading is checked by recompiling.</p>",
    ]
    if found is None:
        return out
    if not found:
        out.append('<p class="dim">No higher reading explains them; they stay note edits.</p>')
        return out
    out.append(
        "<table><tr><th>reading</th><th>edits</th><th>explains</th><th>also changes</th><th></th></tr>"
    )
    for index, suggestion in enumerate(found):
        edits = "<br>".join(_e(f"{e.key} → {e.value}") for e in suggestion.edits)
        out.append(
            f"<tr><td>{_e(suggestion.reason)}</td><td>{edits}</td>"
            f"<td>{len(suggestion.explains)} of {suggestion.in_scope}</td>"
            f"<td>{suggestion.disturbs} untouched note(s)</td>"
            f'<td><form method="post" action="/lift/accept" class="inline">'
            f'<input type="hidden" name="clip" value="{_e(view.key)}">'
            f'<input type="hidden" name="index" value="{index}">'
            f'<input type="hidden" name="back" value="{_e(back)}">'
            f"<button>keep this</button></form></td></tr>"
        )
    out.append("</table>")
    return out


def _variations_html(model: Model, back: str) -> list[str]:
    found = sites(model.overrides)
    if not found:
        return []
    out = [
        "<h2>Variations</h2>",
        '<p class="dim">Alternatives proposed for a place in the song, by you or an agent. '
        "Picking one applies its edits; the source is always an option.</p><table>",
    ]
    for site, alternatives in found.items():
        picked = model.overrides.choices.get(site, SOURCE)
        for name, description in [(SOURCE, "as written")] + [
            (v.name, v.description) for v in alternatives
        ]:
            mark = "●" if name == picked else ""
            button = (
                ""
                if name == picked
                else f'<form method="post" action="/pick" class="inline">'
                f'<input type="hidden" name="site" value="{_e(site)}">'
                f'<input type="hidden" name="name" value="{_e(name)}">'
                f'<input type="hidden" name="back" value="{_e(back)}">'
                f"<button>pick</button></form>"
            )
            out.append(
                f"<tr><td>{_e(site)}</td><td>{mark} {_e(name)}</td>"
                f'<td class="dim">{_e(description)}</td><td>{button}</td></tr>'
            )
    out.append("</table>")
    return out


def _edits_html(model: Model, back: str) -> list[str]:
    edits = model.overrides.edit_list()
    report = model.result.edits
    out = ["<h2>Edits above the notes</h2>"]
    if not edits:
        out.append(
            '<p class="dim">None yet. Edits made here are kept in the song\'s overrides.</p>'
        )
    else:
        out.append("<table>")
        for edit in edits:
            status = "applied"
            if any(s.startswith(edit.key) for s in report.stale):
                status = "stale — the source changed under it"
            if any(s.startswith(edit.key) for s in report.orphaned):
                status = "orphaned — the source no longer has this place"
            out.append(
                f"<tr><td>{_e(edit.key)}</td><td>{_e(edit.base)} → {_e(edit.value)}</td>"
                f'<td class="dim">{_e(status)}</td><td><form method="post" action="/drop" class="inline">'
                f'<input type="hidden" name="key" value="{_e(edit.key)}">'
                f'<input type="hidden" name="back" value="{_e(back)}">'
                f'<button title="Go back to what the source says">drop</button></form></td></tr>'
            )
        out.append("</table>")
    return out


_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>puLang source</title>
<style>
:root { color-scheme: dark; --ink:#d8dde6; --dim:#7d8594; --line:#2a2f3a; --panel:#161a21;
        --accent:#5ab0ff; --warm:#f2b25c; --add:#7fd18b; --del:#ef8a8a; }
body { margin:0; padding:0 14px 14px; background:#0f1217; color:var(--ink);
       font:12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
header { position:sticky; top:0; background:#0f1217; padding:8px 0 6px; z-index:1;
         display:flex; gap:16px; align-items:baseline; border-bottom:1px solid var(--line); }
h1 { font-size:13px; margin:0; color:var(--accent); font-weight:600; }
nav a { color:var(--dim); text-decoration:none; margin-right:12px; }
nav a.on { color:var(--ink); border-bottom:2px solid var(--accent); }
nav a:hover { color:var(--ink); }
h2 { font-size:12px; margin:14px 0 4px; font-weight:600; }
.lvl { font-weight:400; color:#0f1217; background:var(--warm); border-radius:2px; padding:0 4px; }
.dim { color:var(--dim); font-weight:400; }
.where { margin:8px 0 2px; }
.form a { color:var(--accent); text-decoration:none; }
.msg { background:#1d2a1d; border:1px solid #2f4a2f; padding:4px 8px; border-radius:3px; margin:8px 0; }
.tag { color:#0f1217; background:#e7b0ff; border-radius:2px; padding:0 4px; }
.ed { color:#0f1217; background:var(--warm); border-radius:2px; padding:0 4px; margin-left:4px; }
.line { color:var(--dim); font-weight:400; cursor:help; }
.sec { border-top:1px solid var(--line); margin-top:10px; }
table { border-collapse:collapse; }
td, th { border-bottom:1px solid var(--line); padding:2px 8px 2px 0; text-align:left;
         vertical-align:middle; }
th { color:var(--dim); font-weight:400; }
tr.sel td { background:#1b2533; }
form.inline { display:inline; margin:0; }
input, button { background:var(--panel); color:var(--ink); border:1px solid var(--line);
                border-radius:3px; font:inherit; padding:1px 5px; }
input.edited { border-color:var(--warm); }
input:focus { border-color:var(--accent); outline:none; }
button { cursor:pointer; } button:hover { border-color:var(--accent); }
button.small { padding:0 4px; margin-left:2px; }
pre.diff { background:var(--panel); border:1px solid var(--line); padding:6px 8px; overflow-x:auto; }
pre.diff .add { color:var(--add); } pre.diff .del { color:var(--del); } pre.diff .hunk { color:var(--dim); }
</style></head><body>
{body}
<script>
(() => {
  const get = (k, s = localStorage) => { try { return s.getItem(k) || ""; } catch { return ""; } };
  const set = (k, v, s = localStorage) => { try { s.setItem(k, v); } catch { /* per viewer only */ } };
  const clip = new URLSearchParams(location.search).get("clipId") || "";
  // A new selection in kaiDAW shows what produced it; otherwise stay where you were,
  // since kaiDAW reloads this page after every change.
  const fresh = clip && clip !== get("pulang.clip");
  set("pulang.clip", clip);
  const loaded = new Set();
  function show(name) {
    if (!document.getElementById("tab-" + name)) name = "song";
    for (const s of document.querySelectorAll("section.tab")) s.hidden = s.id !== "tab-" + name;
    for (const a of document.querySelectorAll("nav a")) a.classList.toggle("on", a.dataset.tab === name);
    set("pulang.tab", name);
    for (const el of document.querySelectorAll("#tab-" + name + " [data-fragment]")) {
      if (loaded.has(el)) continue;
      loaded.add(el);
      fetch(el.dataset.fragment).then((r) => r.text()).then((h) => { el.innerHTML = h; })
        .catch(() => { el.innerHTML = '<p class="dim">Could not load this part.</p>'; });
    }
    return name;
  }
  const tab = show(fresh ? "selection" : get("pulang.tab") || "song");
  for (const a of document.querySelectorAll("nav a")) {
    a.onclick = (e) => {
      e.preventDefault();
      show(a.dataset.tab);
      const row = a.dataset.tab === "song" && document.querySelector("tr.sel");
      if (row) row.scrollIntoView({ block: "center" }); else scrollTo(0, 0);
    };
  }
  scrollTo(0, Number(get("pulang.scroll." + tab, sessionStorage)) || 0);
  addEventListener("pagehide", () => set("pulang.scroll." + get("pulang.tab"), String(scrollY), sessionStorage));
})();
</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    companion: Companion

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet
        return

    def _send(self, status: int, body: str, kind: str = "text/html; charset=utf-8") -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("content-type", kind)
        self.send_header("content-length", str(len(data)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ("/", "/inspect"):
                self._send(200, self.companion.page(query))
            elif url.path == "/fragment/readings":
                self._send(200, self.companion.readings(query["clip"], query.get("back", "/")))
            elif url.path == "/fragment/fold":
                self._send(200, self.companion.fold_preview(query.get("back", "/")))
            elif url.path == "/health":
                self._send(
                    200,
                    json.dumps({"ok": True, "song": str(self.companion.path)}),
                    "application/json",
                )
            else:
                self._send(404, "not found", "text/plain")
        except Exception:  # noqa: BLE001 — a page that says what broke beats a dead socket
            self._send(500, f"<pre>{_e(traceback.format_exc())}</pre>")

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", 0))
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()}
        back = form.get("back", "/inspect")
        companion = self.companion
        try:
            if self.path == "/edit":
                companion.message = companion.edit(
                    form["level"], form["target"], form["field"], form.get("value", "")
                )
            elif self.path == "/drop":
                companion.message = companion.drop(form["key"])
            elif self.path == "/pick":
                companion.message = companion.pick(form["site"], form["name"])
            elif self.path == "/fold":
                companion.message = companion.fold()
            elif self.path == "/lift/accept":
                companion.message = companion.accept(form["clip"], int(form["index"]))
            else:
                self._send(404, "not found", "text/plain")
                return
        except (ValueError, KeyError, IndexError) as error:
            companion.message = f"Not applied: {error}"
        self.send_response(303)
        self.send_header("location", back)
        self.end_headers()


def serve(song: str | Path, client: KaidawClient | None, listen: int = DEFAULT_LISTEN) -> None:
    """Serve the page until interrupted."""
    handler = type("Handler", (_Handler,), {"companion": Companion(song, client)})
    server = ThreadingHTTPServer(("127.0.0.1", listen), handler)
    print(f"puLang source panel on http://127.0.0.1:{listen} — set it in kaiDAW's source tab")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
