"""
The companion page's views of the whole song: the song as its intent IR, every
value editable where it is shown, and the changes kept beside it.

`pypulang.serve` puts these beside the selection view, under tabs. Each value
says which line of the song set it and whether an edit has changed it since;
folding writes those edits into the source.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from pypulang.compiler.dialects import daw
from pypulang.compiler.edits import plain, section_chart, track_value
from pypulang.dsl import Origin, PieceBuilder
from pypulang.fold import Folding
from pypulang.inspector import Model
from pypulang.motifs import parse_phrase

_HINTS = {
    "voicing": "rootless(52,72), drop2, close… or empty for none",
    "velocity": "1–127",
    "octave": "octaves up or down",
    "muted": "on or off",
    "melody": "motifs and how each is developed: hook; hook +1; hook end 1",
    "pattern": "a pattern name, then its parameters as JSON",
    "chart": "chords, a bar between each |, such as Dm9 G13 | Cmaj9",
    "tempo": "bpm; empty for the piece's",
    "notes": "scale degrees and note values, such as 5/8 6 1'/4 7/8",
    "volume": "0 to 1; 0.74 is unity",
    "pan": "-1 to 1",
}


def _e(value: Any) -> str:
    return html.escape(str(value))


class Fields:
    """Inline edits for one page: each input knows its edit, and says when one changed it."""

    def __init__(self, model: Model, back: str):
        self.edits = {e.key: e for e in model.overrides.edit_list()}
        self.back = back

    def __call__(self, target: str, field: str, value: Any, width: int = 10) -> str:
        shown = "" if value is None else value
        if isinstance(shown, bool):
            shown = "on" if shown else "off"
        edit = self.edits.get(f"intent:{target}:{field}")
        mark = ""
        if edit is not None:
            mark = (
                f'<span class="ed" title="the source says {_e(_text(edit.base))}">edited</span>'
                f'<form method="post" action="/drop" class="inline">'
                f'<input type="hidden" name="key" value="{_e(edit.key)}">'
                f'<input type="hidden" name="back" value="{_e(self.back)}">'
                f'<button class="small" title="Back to what the source says">↺</button></form>'
            )
        return (
            f'<form method="post" action="/edit" class="inline">'
            f'<input type="hidden" name="level" value="intent">'
            f'<input type="hidden" name="target" value="{_e(target)}">'
            f'<input type="hidden" name="field" value="{_e(field)}">'
            f'<input type="hidden" name="back" value="{_e(self.back)}">'
            f'<input name="value" value="{_e(shown)}" size="{width}" '
            f'class="{"edited" if edit else ""}" '
            f'title="{_e(_HINTS.get(field, ""))} (Enter to apply)"></form>{mark}'
        )


def _text(value: Any) -> str:
    if isinstance(value, dict) and "kind" in value:
        return value["kind"] + (
            " " + json.dumps(plain(value["params"])) if value.get("params") else ""
        )
    return "nothing" if value is None else str(value)


class Lines:
    """Which line of the song set a value, from the builders' record of their callers."""

    def __init__(self, builder: PieceBuilder | None, path: Path):
        self.builder = builder
        self.path = os.path.abspath(path)
        try:
            self.text = path.read_text().splitlines()
        except OSError:
            self.text = []

    def tag(self, origin: Origin | None) -> str:
        lines = [line for file, line in origin or () if file == self.path]
        if not lines:
            return ""
        line = lines[-1]
        code = self.text[line - 1].strip() if line <= len(self.text) else ""
        return f'<span class="line" title="{_e(code)}">line {line}</span>'

    def section(self, name: str) -> str:
        section = self._section(name)
        return self.tag(section._origins.get("section")) if section else ""

    def track(self, name: str, track: str) -> str:
        section = self._section(name)
        found = next((t for t in section._tracks if t._name == track), None) if section else None
        return self.tag(found._origins.get("track")) if found else ""

    def motif(self, name: str) -> str:
        return self.tag(self.builder._motif_origins.get(name)) if self.builder else ""

    def rack(self, track: str) -> str:
        return self.tag(self.builder._rack_origins.get(track)) if self.builder else ""

    def _section(self, name: str):
        if self.builder is None:
            return None
        return next((s for s in self.builder._sections if s._name == name), None)


def song_html(model: Model, lines: Lines, back: str, selected: tuple[str, str] | None) -> list[str]:
    """The song as its intent IR, every value an input."""
    piece = model.intent
    key = piece.key.data
    field = Fields(model, back)
    names = [s.section.data for s in piece.sections()]
    form = [f.data for f in piece.form.data] if piece.form is not None else names
    meter = piece.meter.data
    out = [
        f'<p class="where">{_e(key.root)} {_e(key.mode)} · {piece.tempo.value.data:g} bpm · '
        f"{meter.numerator}/{meter.denominator}</p>",
        '<p class="form">' + " · ".join(f'<a href="#s-{_e(n)}">{_e(n)}</a>' for n in form) + "</p>",
    ]
    for section in piece.sections():
        name = section.section.data
        derived = section.derived_from.data if section.derived_from is not None else None
        about = [f"{section.bars.value.data} bars"]
        if section.key is not None:
            about.append(f"{section.key.data.root} {section.key.data.mode}")
        if derived:
            about.append(f"made from {_e(derived)}: follows its edits")
        out.append(
            f'<div class="sec" id="s-{_e(name)}"><h2>{_e(name)} '
            f'<span class="dim">{" · ".join(about)}</span> {lines.section(name)}</h2><table>'
        )
        tempo = f"{section.tempo.value.data:g}" if section.tempo is not None else None
        out.append(f"<tr><td>tempo</td><td>{field(name, 'tempo', tempo, 6)}</td></tr>")
        if section.harmony() is not None:
            out.append(
                f"<tr><td>chart</td><td>{field(f'{name}/harmony', 'chart', section_chart(section, piece), 64)}</td></tr>"
            )
        out.append(
            '</table><table class="parts"><tr><th>part</th><th>plays</th><th>voicing</th>'
            "<th>velocity</th><th>octave</th><th>muted</th><th></th></tr>"
        )
        for track in section.tracks():
            target = f"{name}/{track.track.data}"
            melody = track_value(track, "melody")
            pattern = track_value(track, "pattern")
            if melody is not None:
                plays = field(target, "melody", melody, 36)
            elif pattern is not None:
                plays = field(target, "pattern", _text(pattern), 36)
            else:
                plays = '<span class="dim">written notes</span>'
            chosen = selected == (name, track.track.data)
            out.append(
                f'<tr class="{"sel" if chosen else ""}"><td>{_e(track.track.data)}</td>'
                f"<td>{plays}</td>"
                f"<td>{field(target, 'voicing', track_value(track, 'voicing'), 14)}</td>"
                f"<td>{field(target, 'velocity', track_value(track, 'velocity'), 3)}</td>"
                f"<td>{field(target, 'octave', track_value(track, 'octave'), 2)}</td>"
                f"<td>{field(target, 'muted', track_value(track, 'muted'), 3)}</td>"
                f"<td>{lines.track(name, track.track.data)}</td></tr>"
            )
        out.append("</table></div>")

    motifs = piece.motifs()
    if motifs:
        users: dict[str, list[str]] = {}
        for section in piece.sections():
            for track in section.tracks():
                melody = track_value(track, "melody")
                for placement in parse_phrase(melody) if melody else []:
                    if placement.motif is not None:
                        where = f"{section.section.data}/{track.track.data}"
                        users.setdefault(placement.motif, [])
                        if where not in users[placement.motif]:
                            users[placement.motif].append(where)
        out.append(
            '<div class="sec" id="s-motifs"><h2>Motifs <span class="dim">a change reaches every '
            "melody that uses one</span></h2><table>"
        )
        for name, notes in motifs.items():
            used = ", ".join(users.get(name, [])) or "not used"
            out.append(
                f"<tr><td>{_e(name)}</td><td>{field(f'motif/{name}', 'notes', notes, 36)}</td>"
                f'<td class="dim">{_e(used)}</td><td>{lines.motif(name)}</td></tr>'
            )
        out.append("</table></div>")

    racks = [o for o in piece.body.block.ops if isinstance(o, daw.RackOp)]
    if racks:
        out.append(
            '<div class="sec" id="s-mix"><h2>Mix <span class="dim">each track\'s fader and pan'
            "</span></h2><table><tr><th>track</th><th>volume</th><th>pan</th><th></th></tr>"
        )
        for rack in racks:
            track = rack.track.data
            volume = rack.volume.value.data if rack.volume is not None else None
            pan = rack.pan.value.data if rack.pan is not None else None
            out.append(
                f"<tr><td>{_e(track)}</td><td>{field(f'rack/{track}', 'volume', volume, 5)}</td>"
                f"<td>{field(f'rack/{track}', 'pan', pan, 5)}</td><td>{lines.rack(track)}</td></tr>"
            )
        out.append("</table></div>")
    return out


def fold_html(result: Folding, file: str, back: str) -> str:
    """What folding would write into the song, and a button that does it."""
    if not result.folded and not result.kept:
        return '<p class="dim">Nothing to fold: the source is the whole song.</p>'
    out = []
    if result.folded:
        out.append(
            f"<p>{len(result.folded)} edit(s) can be written into <b>{_e(file)}</b>, "
            "each checked by compiling: the song plays exactly as it does now.</p>"
            f'<form method="post" action="/fold" class="inline">'
            f'<input type="hidden" name="back" value="{_e(back)}">'
            f"<button>Write them into the source</button></form>"
            "<table>"
        )
        out.extend(
            f'<tr><td>{_e(e.key)}</td><td class="dim">{_e(how)}</td></tr>'
            for e, how in result.folded
        )
        out.append("</table>")
    if result.kept:
        out.append("<p>Kept beside the song:</p><table>")
        out.extend(
            f'<tr><td>{_e(e.key)}</td><td class="dim">{_e(why)}</td></tr>' for e, why in result.kept
        )
        out.append("</table>")
    if result.diff:
        rows = []
        for line in result.diff.splitlines():
            kind = (
                "add"
                if line.startswith("+") and not line.startswith("+++")
                else "del"
                if line.startswith("-") and not line.startswith("---")
                else "hunk"
                if line.startswith("@@")
                else ""
            )
            rows.append(f'<span class="{kind}">{_e(line)}</span>')
        out.append('<pre class="diff">' + "\n".join(rows) + "</pre>")
    return "\n".join(out)


def agent_html(available: bool, back: str) -> list[str]:
    """The request form; the runs come in a fragment the page keeps fresh."""
    if not available:
        return [
            '<p class="dim">Asking an agent needs Claude Code (<code>claude</code>) installed '
            "where this page runs.</p>"
        ]
    return [
        '<p class="dim">Claude Code with puLang\'s tools, on this song. It reads the song and '
        "the docs, and changes the song only through puLang's tools, each checked by "
        "compiling. It runs with your Claude Code login, so each request uses your plan.</p>",
        '<form method="post" action="/agent" class="ask">'
        f'<input type="hidden" name="back" value="{_e(back)}">'
        '<textarea name="prompt" rows="3" placeholder="a darker chorus · answer the trumpet in '
        'verse 2 · a calmer bridge"></textarea><div>'
        '<label><input type="radio" name="mode" value="propose" checked> propose alternatives '
        "to pick from</label> "
        '<label><input type="radio" name="mode" value="edit"> make the change</label> '
        "<button>Ask</button></div></form>",
        f'<div data-fragment="/fragment/agent?{_query(back)}" data-poll><p class="dim">…</p></div>',
    ]


def runs_html(runs: list, picked: dict[str, str], back: str) -> str:
    """Each request, newest first: what the agent did and said, and what it proposed."""
    if not runs:
        return '<p class="dim">No requests yet.</p>'
    out = []
    for run in runs:
        state = {
            "running": f"working · {run.seconds:.0f} s",
            "done": f"done in {run.seconds:.0f} s",
            "failed": "failed",
            "stopped": "stopped",
        }[run.status]
        out.append(
            f'<div class="run" {"" if run.handled else "data-running"}>'
            f'<h2>{_e(run.prompt)} <span class="dim">{_e(run.mode)} · {_e(state)}</span>'
        )
        if run.status == "running":
            out.append(
                '<form method="post" action="/agent/stop" class="inline">'
                f'<input type="hidden" name="back" value="{_e(back)}">'
                '<button class="small">stop</button></form>'
            )
        out.append("</h2>")
        if run.answer:
            out.append(f'<p class="answer">{_e(run.answer)}</p>')
        if run.proposed:
            out.append("<table>")
            for site, name in run.proposed:
                mark = "● picked" if picked.get(site) == name else ""
                button = (
                    ""
                    if mark
                    else '<form method="post" action="/pick" class="inline">'
                    f'<input type="hidden" name="site" value="{_e(site)}">'
                    f'<input type="hidden" name="name" value="{_e(name)}">'
                    f'<input type="hidden" name="back" value="{_e(back)}">'
                    "<button>pick and hear it</button></form>"
                )
                out.append(
                    f"<tr><td>{_e(site)}</td><td>{_e(name)}</td><td>{mark}{button}</td></tr>"
                )
            out.append("</table>")
            sites = sorted({site for site, _ in run.proposed})
            out.append(
                '<p class="dim">Pick one and play it in kaiDAW; picking <b>source</b> in the '
                "changes view goes back to the song as written. "
                + ", ".join(f"{_e(s)}: {_e(picked.get(s, 'source'))}" for s in sites)
                + "</p>"
            )
        if run.edited:
            out.append('<p class="dim">Changed: ' + ", ".join(_e(k) for k in run.edited) + "</p>")
        steps = [s for s in run.steps if s != run.answer.strip()]
        if steps:
            shown = steps[-40:]
            out.append(
                f"<details {'open' if run.status == 'running' else ''}><summary>"
                f"{len(steps)} step(s)</summary><ol>"
                + "".join(f"<li>{_e(step)}</li>" for step in shown)
                + "</ol></details>"
            )
        out.append("</div>")
    return "\n".join(out)


def _query(back: str) -> str:
    from urllib.parse import urlencode

    return urlencode({"back": back})
