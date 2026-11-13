"""
Folding edits into the song: rewriting the song's Python so that the edits kept
beside it in its overrides become part of its source.

An edit made in the DAW, in the companion page, or by an agent is kept in the
song's overrides at the level it was made at. Folding writes it where a person
would have: the argument of the call that set it, or a new line after the one
that did. Every rewrite is checked by compiling: an edit is folded only when the
new source, with the edits still kept, compiles to exactly what the old source
did with all of them. What no rewrite reproduces stays in the overrides, with
the reason.

    pulang fold song.py           # rewrite, and say what was folded
    pulang fold song.py --dry-run # show the change without writing it
"""

from __future__ import annotations

import ast
import difflib
import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from pypulang.backends.kaidaw.state import SongState
from pypulang.compiler.edits import Edit, _parse_target, plain, section_chart
from pypulang.dsl import Origin, PieceBuilder, SectionBuilder, TrackBuilder
from pypulang.songfile import load_song
from pypulang.variations import song_edits

# The builder call that sets each track field.
_SETTERS = {
    "velocity": ("velocity",),
    "octave": ("octave",),
    "voicing": ("voicing",),
    "pattern": ("pattern",),
    "melody": ("melody",),
    "muted": ("mute", "unmute"),
}


@dataclass
class Folding:
    """What `fold` did, or would do."""

    source: str
    folded: list[tuple[Edit, str]] = field(default_factory=list)
    kept: list[tuple[Edit, str]] = field(default_factory=list)
    diff: str = ""

    def lines(self) -> list[str]:
        out = [f"Folded {e.key}: {how}" for e, how in self.folded]
        out += [f"Kept {e.key}: {why}" for e, why in self.kept]
        return out


def fold(song: str | Path, write: bool = True) -> Folding:
    """
    Fold the song's edits into its source.

    Args:
        song: The song's .py file
        write: Rewrite the song and its overrides; False only reports
    """
    path = Path(song).resolve()
    original = path.read_text()
    state = SongState.beside(path)
    overrides = state.load_overrides()
    everything = song_edits(overrides)
    # Each rewrite is checked against the intent IR, which is all a source change
    # can reach and twenty times quicker to compile; the result once more in full.
    expected = _fingerprint(path, everything, "intent")
    if expected is None:
        raise ValueError(f"{path.name} does not compile as it is; fix it before folding")

    result = Folding(original)
    remaining = list(everything)
    scratch = path.with_name(f".{path.stem}.fold.py")
    try:
        for edit in overrides.edit_list():
            if edit.level != "intent":
                result.kept.append((edit, "below the source's level: it places notes, not calls"))
                continue
            applied = _find(remaining, edit)
            rest = [e for e in remaining if e is not applied]
            reason = "no call in the song sets it"
            for how, text in _rewrites(edit, result.source, scratch):
                scratch.write_text(text)
                if _fingerprint(scratch, rest, "intent") == expected:
                    result.source = text
                    result.folded.append((edit, how))
                    remaining = rest
                    break
                reason = "every rewrite tried also changes something else"
            else:
                result.kept.append((edit, reason))
        if result.folded:
            scratch.write_text(result.source)
            if _fingerprint(scratch, remaining) != _fingerprint(path, everything):
                kept = [
                    (e, "the folded song did not compile the same in full")
                    for e, _ in result.folded
                ]
                result = Folding(original, [], kept + result.kept)
    finally:
        scratch.unlink(missing_ok=True)

    result.diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            result.source.splitlines(keepends=True),
            fromfile=path.name,
            tofile=path.name,
        )
    )
    if write and result.folded:
        path.write_text(result.source)
        folded = {e.key for e, _ in result.folded}
        overrides.edits = [e for e in overrides.edits if Edit.from_json(e).key not in folded]
        state.save_overrides(overrides)
    return result


def _find(edits: list[Edit], edit: Edit) -> Edit | None:
    """The hand edit in a compile's list: the last with its key, as the compile applies it."""
    return next((e for e in reversed(edits) if e.key == edit.key and e.origin is None), None)


def _fingerprint(path: Path, edits: list[Edit], until: str = "daw") -> str | None:
    """What a song compiles to with some edits, or None if it does not compile."""
    try:
        result = load_song(path).compile(edits=edits, until=until)
    except Exception:
        return None
    if until == "intent":
        return str(result.stages["intent"])
    return str(result.stages["event"]) + str(result.daw)


# --- the rewrites to try for an edit ------------------------------------------


def _rewrites(edit: Edit, text: str, scratch: Path) -> Iterator[tuple[str, str]]:
    """(what was done, the new source) for each rewrite worth trying, smallest first."""
    scratch.write_text(text)
    song = _Song(text, scratch, _builder(scratch))
    if edit.target.startswith("motif/"):
        yield from song.motif(edit.target.removeprefix("motif/"), str(edit.value))
        return
    if edit.target.startswith("rack/"):
        yield from song.rack(edit.target.removeprefix("rack/"), edit.field, edit.value)
        return
    name, _, rest = _parse_target(edit.target)
    section = next((s for s in song.piece._sections if s._name == name), None)
    if section is None:
        return
    if rest == "":
        yield from song.tempo(section, edit.value)
    elif rest.startswith("harmony"):
        chart = _chart_after(scratch, edit) if rest != "harmony" else str(edit.value)
        if chart is not None:
            yield from song.chart(section, chart, rest)
    else:
        track = next((t for t in section._tracks if t._name == rest), None)
        if track is not None and edit.field in _SETTERS:
            yield from song.track_field(section, track, edit.field, edit.value)


def _builder(path: Path) -> PieceBuilder:
    builder = load_song(path).builder
    if builder is None:
        raise ValueError(f"{path}: only a song written in Python can be folded into")
    return builder


def _chart_after(path: Path, edit: Edit) -> str | None:
    """The section's chart with one chord edit applied, as a chart edit would set it."""
    from pypulang.compiler.edits import _intent_section, _piece

    try:
        result = load_song(path).compile(until="intent", edits=[edit])
    except Exception:
        return None
    piece = _piece(result.stages["intent"])
    section = _intent_section(piece, _parse_target(edit.target)[0])
    return section_chart(section, piece) if section is not None else None


class _Song:
    """A song's source and the builders it made, to find the calls that set things."""

    def __init__(self, text: str, path: Path, piece: PieceBuilder):
        self.text = text
        self.path = os.path.abspath(path)
        self.piece = piece
        self.tree = ast.parse(text)
        self.lines = text.splitlines(keepends=True)
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line))

    # --- positions

    def at(self, line: int, col: int) -> int:
        """A character offset from an AST position, whose column counts UTF-8 bytes."""
        return self.starts[line - 1] + len(self.lines[line - 1].encode()[:col].decode())

    def span(self, node: ast.AST) -> tuple[int, int]:
        return self.at(node.lineno, node.col_offset), self.at(node.end_lineno, node.end_col_offset)

    def replaced(self, start: int, end: int, new: str) -> str:
        return self.text[:start] + new + self.text[end:]

    def lines_of(self, origin: Origin | None) -> list[int]:
        """The song's own lines in an origin, innermost first."""
        return [line for file, line in origin or () if file == self.path]

    def call(self, origin: Origin | None, methods: tuple[str, ...]) -> ast.Call | None:
        """The call to one of `methods` that the origin's innermost song line is part of."""
        lines = self.lines_of(origin)
        if not lines:
            return None
        found = [
            n
            for n in ast.walk(self.tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in methods
            and n.lineno <= lines[0] <= n.end_lineno
        ]
        return min(found, key=lambda n: self.span(n)[1] - self.span(n)[0], default=None)

    def method_span(self, call: ast.Call) -> tuple[int, int]:
        """From the dot before a method's name to the end of its call: `.velocity(80)`."""
        return self.span(call.func.value)[1], self.span(call)[1]

    def statement(self, line: int) -> tuple[list[ast.stmt], ast.stmt] | None:
        """The innermost block holding a statement on `line`, and that statement."""
        best = None
        for node in ast.walk(self.tree):
            for name in ("body", "orelse", "finalbody"):
                block = getattr(node, name, None)
                if not isinstance(block, list):
                    continue
                for stmt in block:
                    if isinstance(stmt, ast.stmt) and stmt.lineno <= line <= stmt.end_lineno:
                        if best is None or stmt.lineno >= best[1].lineno:
                            best = (block, stmt)
        return best

    def variable(self, section: SectionBuilder) -> tuple[str, list[ast.stmt]] | None:
        """The name the song keeps a section in, and the block it was made in."""
        lines = self.lines_of(section._origins.get("section"))
        if not lines:
            return None
        found = self.statement(lines[-1])
        if found is None:
            return None
        block, stmt = found
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
        ):
            return stmt.targets[0].id, block
        return None

    def anchor(self, block: list[ast.stmt], origins: list[Origin | None]) -> ast.stmt | None:
        """The statement in `block` that made the latest of `origins`."""
        lines = [ls[-1] for ls in (self.lines_of(o) for o in origins) if ls]
        anchors = [s for s in block for line in lines if s.lineno <= line <= s.end_lineno]
        return max(anchors, key=lambda s: s.end_lineno, default=None)

    def following(self, block: list[ast.stmt], origins: list[Origin | None]) -> ast.stmt | None:
        """The statement right after the anchor, where an earlier fold may have put a line."""
        anchor = self.anchor(block, origins)
        if anchor is None or block.index(anchor) + 1 >= len(block):
            return None
        return block[block.index(anchor) + 1]

    def arguments(self, call: ast.Call, codes: list[str]) -> str:
        """The source with each positional argument of a call replaced, keeping its layout."""
        text = self.text
        for node, code in sorted(
            zip(call.args, codes, strict=True), key=lambda p: -self.span(p[0])[0]
        ):
            start, end = self.span(node)
            text = text[:start] + code + text[end:]
        return text

    def append_after(self, block: list[ast.stmt], origins: list[Origin | None], code: str):
        """
        A new line after the statement in `block` that made the latest of `origins`,
        so it runs after whatever set the thing before.
        """
        anchor = self.anchor(block, origins)
        if anchor is None:
            return None
        end = self.at(anchor.end_lineno, anchor.end_col_offset)
        return self.replaced(end, end, "\n" + " " * anchor.col_offset + code)

    # --- literals behind an argument

    def literal_of(self, node: ast.expr) -> ast.Constant | None:
        """A string argument's literal: itself, or a module constant it names."""
        if isinstance(node, ast.Constant):
            return node
        if isinstance(node, ast.Name):
            values = [
                s.value
                for s in self.tree.body
                if isinstance(s, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == node.id for t in s.targets)
            ]
            if len(values) == 1 and isinstance(values[0], ast.Constant):
                return values[0]
        return None

    def literals_equal(self, value: str) -> list[ast.Constant]:
        return [
            n
            for n in ast.walk(self.tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value == value
        ]

    def argument(self, call: ast.Call, index: int, keyword: str | None, code: str) -> str:
        """The source with one argument of a call replaced, or added as a keyword."""
        if index < len(call.args):
            return self.replaced(*self.span(call.args[index]), code)
        for kw in call.keywords:
            if kw.arg == keyword:
                return self.replaced(*self.span(kw.value), code)
        last = max([*call.args, *(k.value for k in call.keywords)], key=lambda n: self.span(n)[1])
        end = self.span(last)[1]
        return self.replaced(end, end, f", {keyword}={code}")

    # --- rewrites by kind

    def motif(self, name: str, notes: str) -> Iterator[tuple[str, str]]:
        call = self.call(self.piece._motif_origins.get(name), ("motif",))
        if call is not None and len(call.args) > 1:
            literal = self.literal_of(call.args[1])
            if literal is not None:
                yield f"motif {name!r} rewritten", self.replaced(*self.span(literal), _code(notes))
        # Motifs named in a loop over a dict: the dict's literal, if it is the only one
        current = self.piece._motifs.get(name)
        if current is not None:
            matches = self.literals_equal(current)
            if len(matches) == 1:
                yield (
                    f"motif {name!r} rewritten",
                    self.replaced(*self.span(matches[0]), _code(notes)),
                )

    def rack(self, track: str, name: str, value: Any) -> Iterator[tuple[str, str]]:
        call = self.call(self.piece._rack_origins.get(track), ("rack",))
        if call is None or name not in ("volume", "pan") or value in (None, ""):
            return
        yield f"{track}'s rack {name} set", self.argument(call, 99, name, _code(float(value)))

    def tempo(self, section: SectionBuilder, value: Any) -> Iterator[tuple[str, str]]:
        call = self.call(section._origins.get("section"), ("section",))
        if call is None or value in (None, ""):
            return
        yield f"{section._name}'s tempo set", self.argument(call, 99, "tempo", _code(value))

    def chart(self, section: SectionBuilder, chart: str, rest: str) -> Iterator[tuple[str, str]]:
        name = section._name
        call = self.call(section._origins.get("harmony"), ("chart", "harmony", "progression"))
        if call is not None and call.func.attr == "chart" and call.args:
            literal = self.literal_of(call.args[0])
            if literal is not None and isinstance(literal.value, str):
                if rest != "harmony":
                    token = _chart_token_change(literal.value, chart)
                    if token is not None:
                        yield (
                            f"{name}'s chart: one chord changed",
                            self.replaced(*self.span(literal), _code(token)),
                        )
                yield f"{name}'s chart rewritten", self.replaced(*self.span(literal), _code(chart))
            if literal is not call.args[0] or literal is None:
                yield (
                    f"{name}'s chart written at its call",
                    self.replaced(*self.span(call.args[0]), _code(chart)),
                )
        elif call is not None:
            yield (
                f"{name}'s harmony written as a chart",
                self.replaced(*self.method_span(call), f".chart({_code(chart)})"),
            )
        found = self.variable(section)
        if found is not None:
            variable, block = found
            origins = [section._origins.get("section"), section._origins.get("harmony")]
            text = self.append_after(block, origins, f"{variable}.chart({_code(chart)})")
            if text is not None:
                yield f"{name}'s chart set on a new line", text

    def track_field(
        self, section: SectionBuilder, track: TrackBuilder, name: str, value: Any
    ) -> Iterator[tuple[str, str]]:
        where = f"{section._name}/{track._name}"
        setter = _setter(name, value)
        if setter is None:
            return
        call = self.call(track._origins.get(name), _SETTERS[name])
        if call is not None:
            if name in ("melody",) and call.args:
                literal = self.literal_of(call.args[0])
                if literal is not None and literal is not call.args[0]:
                    yield (
                        f"{where} {name} rewritten",
                        self.replaced(*self.span(literal), _code(value)),
                    )
                yield (
                    f"{where} {name} written at its call",
                    self.replaced(*self.span(call.args[0]), _code(value)),
                )
            elif name != "melody":
                args = _setter_args(name, value)
                if args is not None and len(args) == len(call.args) and not call.keywords:
                    yield f"{where} {name} set", self.arguments(call, args)
                yield f"{where} {name} set", self.replaced(*self.method_span(call), setter)
        else:
            made = self.call(track._origins.get("track"), ("track",))
            if made is not None:
                end = self.span(made)[1]
                yield f"{where} {name} added", self.replaced(end, end, setter)
        found = self.variable(section)
        if found is not None:
            variable, block = found
            origins = [
                track._origins.get("track"),
                track._origins.get(name),
                section._origins.get("section"),
            ]
            line = f"{variable}.track({_code(track._name)})"
            following = self.following(block, origins)
            if isinstance(following, ast.Expr) and self.text[
                slice(*self.span(following))
            ].startswith(line):
                end = self.span(following)[1]
                yield f"{where} {name} set on the line after", self.replaced(end, end, setter)
            text = self.append_after(block, origins, line + setter)
            if text is not None:
                yield f"{where} {name} set on a new line", text


# --- values as source ----------------------------------------------------------

_FRACTION = re.compile(r"^-?\d+/\d+$")


def _code(value: Any) -> str:
    """A value as Python source."""
    if isinstance(value, bool):
        return repr(value)
    if isinstance(value, str) and _FRACTION.match(value):
        return _code(Fraction(value))
    if isinstance(value, Fraction):
        if Fraction(str(float(value))) == value:
            return repr(float(value))
        return f"Fraction({value.numerator}, {value.denominator})"
    if isinstance(value, float):
        return repr(int(value)) if value.is_integer() and abs(value) >= 20 else repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(plain(value))


def _setter_args(name: str, value: Any) -> list[str] | None:
    """A setter's arguments alone, to replace those of a call written across lines."""
    if name in ("velocity", "octave"):
        return [str(int(value))]
    if name == "voicing":
        match = re.fullmatch(r"(\w+)(?:\((-?\d+),(-?\d+)\))?", str(value or ""))
        if match is None:
            return None
        strategy, low, high = match.groups()
        return [_code(strategy), low, high] if low else [_code(strategy)]
    return None


def _setter(name: str, value: Any) -> str | None:
    """The chained call that sets a track field to a value."""
    if name in ("velocity", "octave"):
        return f".{name}({int(value)})"
    if name == "muted":
        return ".mute()" if value else ".unmute()"
    if name == "voicing":
        if value in (None, ""):
            return None
        match = re.fullmatch(r"(\w+)(?:\((-?\d+),(-?\d+)\))?", str(value))
        if match is None:
            return None
        strategy, low, high = match.groups()
        return f".voicing({_code(strategy)}" + (f", {low}, {high})" if low else ")")
    if name == "pattern":
        params = value.get("params") or {}
        from pypulang.dsl import _NOTE_VALUE_PARAMS

        args = ", ".join(
            f"{k}={_code(Fraction(plain(v)) / 4 if k in _NOTE_VALUE_PARAMS else v)}"
            for k, v in params.items()
        )
        return f".pattern({value['kind']}({args}))" if args else f".pattern({value['kind']})"
    if name == "melody":
        return f".melody({_code(value)})"
    return None


def _chart_token_change(written: str, chart: str) -> str | None:
    """
    The written chart with the one chord that differs from `chart` replaced, keeping
    how the rest was written: its spellings, spacing and repeats.
    """
    old = [b.split() for b in written.split("|")]
    new = [b.split() for b in chart.split("|")]
    if len(old) != len(new) or any(len(a) != len(b) for a, b in zip(old, new, strict=True)):
        return None
    changed = [
        (i, j)
        for i, (a, b) in enumerate(zip(old, new, strict=True))
        for j, (x, y) in enumerate(zip(a, b, strict=True))
        if x != y and x != "%"
    ]
    if not changed:
        return None
    bars = written.split("|")
    for i, j in changed:
        tokens = bars[i].split()
        spaced = re.split(r"(\s+)", bars[i])
        count = -1
        for k, piece in enumerate(spaced):
            if piece and not piece.isspace():
                count += 1
                if count == j:
                    spaced[k] = new[i][j]
        bars[i] = "".join(spaced)
        assert len(tokens) == len(bars[i].split())
    return "|".join(bars)
