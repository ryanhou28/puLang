"""
A Model Context Protocol server for puLang: `pulang mcp`.

It speaks MCP over stdio (one JSON-RPC message per line) and offers the tools in
`pypulang.agent`, so an agent such as Claude Code can read a song, edit it at a
level, propose variations and render windows. Register it with

    claude mcp add pulang -- pulang mcp

Every tool takes the song's path. A tool that fails returns its reason as an
error result, which the agent reads like any other answer.
"""

from __future__ import annotations

import contextlib
import json
import sys
import traceback
from typing import Any, TextIO

from pypulang import agent

PROTOCOL = "2025-06-18"

_SONG = {"type": "string", "description": "Path to the song's .py file"}
_EDIT = {
    "type": "object",
    "properties": {
        "level": {"type": "string", "enum": ["intent", "score"], "default": "intent"},
        "target": {
            "type": "string",
            "description": 'Such as "chorus/harmony", "motif/hook", "verse/keys", "rack/piano" for its volume or pan, or "outro" for its tempo',
        },
        "field": {
            "type": "string",
            "description": "chart, chord, notes, melody, pattern, voicing, octave, velocity, muted, pitches, tempo, volume, pan",
        },
        "value": {
            "description": "The new value: text as the song writes it, or a number or boolean"
        },
    },
    "required": ["target", "field", "value"],
}


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"song": _SONG, **properties},
        "required": ["song", *required],
    }


TOOLS: list[dict[str, Any]] = [
    {
        "name": "describe",
        "description": "Read a song in one go: tempo, key, form with bars and times, each section's chord chart and every track's part (melody phrase, pattern, voicing), motifs, edits and variations.",
        "inputSchema": _schema({}, []),
    },
    {
        "name": "ir",
        "description": "Print the song's IR at one compiler stage (intent, score, event, daw), optionally only one section.",
        "inputSchema": _schema(
            {
                "stage": {
                    "type": "string",
                    "enum": ["intent", "score", "event", "daw"],
                    "default": "intent",
                },
                "section": {"type": "string", "description": "A section name, such as chorus"},
            },
            [],
        ),
    },
    {
        "name": "review",
        "description": "The compiler's read-through of the music (melody against harmony, ranges, parallels) and each melody's range and density per section.",
        "inputSchema": _schema({}, []),
    },
    {
        "name": "variations",
        "description": "Every variation site, its proposed alternatives, and which one is picked.",
        "inputSchema": _schema({}, []),
    },
    {
        "name": "edit",
        "description": "Change one thing above the notes and keep it beside the song: a section's chart, a chord, a motif's notes, a track's melody phrase, pattern, voicing, octave, velocity or mute. Checked by compiling; reports the notes it changes.",
        "inputSchema": _schema(dict(_EDIT["properties"]), ["target", "field", "value"]),
    },
    {
        "name": "drop",
        "description": 'Forget an edit, named "level:target:field".',
        "inputSchema": _schema({"key": {"type": "string"}}, ["key"]),
    },
    {
        "name": "fold",
        "description": "Write the hand edits into the song's source where a person would have made them, and drop them from its overrides. Each is checked by compiling; returns what was folded, what was kept and why, and the diff.",
        "inputSchema": _schema({"dry_run": {"type": "boolean", "default": False}}, []),
    },
    {
        "name": "propose",
        "description": 'Keep an alternative at a site (such as "chorus hook") as a named bundle of edits, without picking it. Checked by compiling; reports the notes it changes against the source.',
        "inputSchema": _schema(
            {
                "site": {"type": "string"},
                "name": {"type": "string"},
                "edits": {"type": "array", "items": _EDIT, "minItems": 1},
                "description": {"type": "string"},
                "author": {"type": "string", "default": "agent"},
            },
            ["site", "name", "edits"],
        ),
    },
    {
        "name": "pick",
        "description": 'Choose an alternative at a site; "source" goes back to the song as written.',
        "inputSchema": _schema(
            {"site": {"type": "string"}, "name": {"type": "string"}}, ["site", "name"]
        ),
    },
    {
        "name": "drop_variation",
        "description": "Forget a proposed variation.",
        "inputSchema": _schema({"name": {"type": "string"}}, ["name"]),
    },
    {
        "name": "readings",
        "description": 'Pull the hand edits made in kaiDAW and read those in one clip (such as "chorus#1/trumpet") as edits above the notes: a chord, a voicing, an octave, a motif rewritten, a phrase moved. Each is checked by recompiling; explains counts the hand edits it reproduces, disturbs the untouched notes it would also change.',
        "inputSchema": _schema(
            {
                "clip": {"type": "string"},
                "port": {"type": "integer"},
                "pull_first": {"type": "boolean", "default": True},
            },
            ["clip"],
        ),
    },
    {
        "name": "keep_reading",
        "description": "Keep one reading from `readings`: its edits are kept and the note edits it explains are dropped.",
        "inputSchema": _schema(
            {"clip": {"type": "string"}, "index": {"type": "integer", "minimum": 0}},
            ["clip", "index"],
        ),
    },
    {
        "name": "render",
        "description": 'Push the song to a running kaiDAW and bounce a window to a WAV: a section occurrence such as "chorus#2", or bars, or the whole song. Returns the file and its RMS and peak levels.',
        "inputSchema": _schema(
            {
                "out": {"type": "string", "description": "WAV path to write"},
                "section": {"type": "string"},
                "start_bar": {"type": "integer", "minimum": 1},
                "bars": {"type": "integer", "minimum": 1, "default": 8},
                "port": {"type": "integer", "description": "kaiDAW's port"},
            },
            ["out"],
        ),
    },
    {
        "name": "audition",
        "description": "Render the source and every alternative at a site over the same window, through a running kaiDAW, for a person to compare. The song is left as picked.",
        "inputSchema": _schema(
            {
                "site": {"type": "string"},
                "out_dir": {"type": "string"},
                "section": {
                    "type": "string",
                    "description": 'An occurrence to hear it in, such as "chorus#1"',
                },
                "port": {"type": "integer"},
            },
            ["site", "out_dir"],
        ),
    },
]


def usage(name: str) -> str:
    """A tool's arguments, required ones first, each with what it is."""
    tool = next((t for t in TOOLS if t["name"] == name), None)
    if tool is None:
        return f"No tool {name!r}; tools are {', '.join(t['name'] for t in TOOLS)}"
    schema = tool["inputSchema"]
    required = schema.get("required", [])
    lines = [f"{name}: {tool['description']}"]
    for arg, spec in sorted(schema["properties"].items(), key=lambda kv: kv[0] not in required):
        kind = spec.get("type", "any")
        note = spec.get("description", "")
        default = f" (default {spec['default']})" if "default" in spec else ""
        lines.append(
            f"  {arg}: {kind}{', required' if arg in required else ''}{default}  {note}".rstrip()
        )
    return "\n".join(lines)


def _bad_arguments(name: str, arguments: dict[str, Any]) -> str | None:
    """What is wrong with a call's arguments, or None if they fit the tool."""
    import inspect

    try:
        inspect.signature(agent.TOOLS[name]).bind(**arguments)
    except TypeError as error:
        return f"{error}\n{usage(name)}"
    return None


def call(name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
    """Run one tool. Returns the text of its answer and whether it failed."""
    tool = agent.TOOLS.get(name)
    if tool is None:
        return f"No tool {name!r}", True
    if (bad := _bad_arguments(name, arguments)) is not None:
        return bad, True
    try:
        # Anything a tool prints would corrupt the message stream on stdout.
        with contextlib.redirect_stdout(sys.stderr):
            result = tool(**arguments)
    except agent.ToolError as error:
        return str(error), True
    except TypeError as error:
        return f"{name}: {error}", True
    except Exception as error:  # noqa: BLE001 — the agent should see what broke
        return f"{name} failed: {error}\n{traceback.format_exc(limit=3)}", True
    text = result if isinstance(result, str) else json.dumps(agent.plain(result), indent=1)
    return text, False


def _answer(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    ident = message.get("id")
    if ident is None:
        return None  # a notification, such as notifications/initialized
    if method == "initialize":
        asked = message.get("params", {}).get("protocolVersion", PROTOCOL)
        result: dict[str, Any] = {
            "protocolVersion": asked,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "pulang", "version": "0.1"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params", {})
        text, failed = call(params.get("name", ""), params.get("arguments") or {})
        result = {"content": [{"type": "text", "text": text}], "isError": failed}
    elif method == "ping":
        result = {}
    else:
        return {
            "jsonrpc": "2.0",
            "id": ident,
            "error": {"code": -32601, "message": f"No method {method}"},
        }
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def serve(reader: TextIO = sys.stdin, writer: TextIO = sys.stdout) -> None:
    """Answer messages until the input closes."""
    for line in reader:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            reply: dict[str, Any] | None = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Not JSON"},
            }
        else:
            reply = _answer(message)
        if reply is not None:
            writer.write(json.dumps(reply) + "\n")
            writer.flush()
