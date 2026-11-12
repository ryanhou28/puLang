"""
The `pulang` command.

    pulang ir song.py --stage score       Print the IR at a stage
    pulang check song.py                  Read through the music for likely mistakes
    pulang trace song.py -o build/        Write the IR after every pass
    pulang midi song.py -o song.mid       Write a MIDI file
    pulang push song.py                   Make kaiDAW hold the song
    pulang status song.py                 Say what a push would do
    pulang pull song.py                   Keep edits made in the DAW
    pulang save song.py <path>            Save the project the server has open
    pulang edits song.py                  List those edits
    pulang drop song.py <location>        Forget one of them
    pulang render song.py -o song.wav     Bounce it
    pulang stems song.py -o stems/        Bounce each track alone, and measure them
    pulang watch song.py                  Push every time the file is saved
    pulang serve song.py                  Show the IR beside kaiDAW, and edit it there
    pulang variations song.py             List each site's alternatives and which is picked
    pulang propose song.py SITE NAME EDIT Keep an alternative, such as motif/hook:notes="..."
    pulang pick song.py SITE NAME         Choose one, or "source"
    pulang audition song.py SITE -o dir/  Render every alternative at a site
    pulang agent TOOL '{"song": ...}'     Run one agent tool: JSON in, JSON out
    pulang mcp                            Serve the agent tools over MCP on stdio
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from fractions import Fraction
from pathlib import Path

from pypulang import analysis
from pypulang.backends.kaidaw import KaidawClient, KaidawError, SongState, pull, push, status
from pypulang.backends.kaidaw.client import DEFAULT_PORT, WslTransport
from pypulang.backends.kaidaw.sync import MASTER
from pypulang.backends.midi import event_to_midi
from pypulang.compiler import print_ir
from pypulang.compiler.check import review
from pypulang.compiler.dialects import event as event_dialect
from pypulang.compiler.pipeline import STAGES
from pypulang.songfile import Song, load_song


def _client(args: argparse.Namespace) -> KaidawClient:
    return KaidawClient(port=args.port)


def _state(args: argparse.Namespace) -> SongState:
    return SongState.beside(args.song)


def _report(song: Song, result_warnings: list[str]) -> None:
    for warning in result_warnings:
        print(f"warning: {warning}", file=sys.stderr)


def cmd_ir(args: argparse.Namespace) -> int:
    result = load_song(args.song).compile(until=args.stage)
    print(print_ir(result.stages[args.stage], locations=args.locations), end="")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    module = load_song(args.song).compile(until="score").stages["score"]
    print(review(module).summary())
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    result = load_song(args.song).compile(keep_trace=True)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    for index, (name, module) in enumerate(result.trace):
        (out / f"{index:02d}-{name}.mlir").write_text(print_ir(module, locations=True))
    for stage, module in result.stages.items():
        (out / f"{stage}.mlir").write_text(print_ir(module, locations=True))
    print(f"Wrote {len(result.trace) + len(result.stages)} files to {out}")
    return 0


def cmd_midi(args: argparse.Namespace) -> int:
    result = load_song(args.song).compile(until="event")
    event_to_midi(result.stages["event"]).save(args.output)
    print(f"Wrote {args.output}")
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    song = load_song(args.song)
    result = song.compile()
    report = push(result.daw, _client(args), _state(args), fresh=args.fresh)
    _report(song, result.warnings)
    print(report.summary())
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    song = load_song(args.song)
    result = song.compile()
    report = status(result.daw, _client(args), _state(args))
    _report(song, result.warnings)
    print(report.summary())
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    report = pull(_client(args), _state(args))
    print(f"Captured {report.captured} edit(s)")
    return 0


def cmd_save(args: argparse.Namespace) -> int:
    """Save the open project, so it can be reopened in kaiDAW and pushed to again."""
    client = _client(args)
    transport = client.transport
    if isinstance(transport, WslTransport) and args.path[1:3] == ":\\":
        # The server creates the project's files but not its directory.
        drive = args.path[0].lower()
        Path(f"/mnt/{drive}/{args.path[3:].replace(chr(92), '/')}").mkdir(
            parents=True, exist_ok=True
        )
    client.save(args.path)
    print(f"Saved {args.path}")
    return 0


def cmd_edits(args: argparse.Namespace) -> int:
    overrides = _state(args).load_overrides()
    for location, entry in sorted(overrides.notes.items()):
        if entry.get("deleted"):
            print(f"deleted  {location}")
        else:
            print(f"edited   {location}: {entry['base']} -> {entry['note']}")
    for clip, notes in sorted(overrides.added.items()):
        for item in notes:
            print(f"drawn    {clip}: {item['note']}")
    for clip, directive in sorted(overrides.clips.items()):
        print(f"clip     {clip}: {directive}")
    for edit in overrides.edit_list():
        print(f"{edit.level:8s} {edit.key}: {edit.base!r} -> {edit.value!r}")
    if not overrides.count:
        print("No edits.")
    return 0


def cmd_drop(args: argparse.Namespace) -> int:
    state = _state(args)
    overrides = state.load_overrides()
    # An edit above the notes is named "level:target:field", as `pulang edits` lists it.
    if not overrides.drop_edit(args.location) and overrides.notes.pop(args.location, None) is None:
        print(f"No edit at {args.location}", file=sys.stderr)
        return 1
    state.save_overrides(overrides)
    print(f"Dropped {args.location}. The next push restores what the source makes there.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from pypulang.serve import serve

    client = None if args.offline else _client(args)
    serve(args.song, client, args.listen)
    return 0


def _seconds(song: Song) -> float:
    """How long a piece runs, from its section markers and first tempo."""
    module = song.compile(until="event").stages["event"]
    stream = next(o for o in module.body.block.ops if isinstance(o, event_dialect.StreamOp))
    end = max((s.at.data + s.length.data for s in stream.sections()), default=Fraction(0))
    bpm = stream.tempos()[0].bpm.value.data
    return float(end) * 60 / bpm


def cmd_render(args: argparse.Namespace) -> int:
    song = load_song(args.song)
    client = _client(args)
    result = song.compile()
    report = push(result.daw, client, _state(args), fresh=args.fresh)
    print(report.summary())

    seconds = _seconds(song) + args.tail
    transport = client.transport
    if isinstance(transport, WslTransport):
        name = f"pulang-{Path(args.output).stem}.wav"
        rendered = client.render(f"{transport.share_win}\\{name}", 0.0, seconds)
        shutil.move(str(transport.share_wsl / name), args.output)
    else:
        rendered = client.render(str(Path(args.output).resolve()), 0.0, seconds)
    print(f"Rendered {rendered['audioSeconds']:.1f}s to {args.output}, peak {rendered['peak']:.3f}")
    return 0


def _render_to(client: KaidawClient, output: Path, start: float, seconds: float) -> dict:
    transport = client.transport
    if isinstance(transport, WslTransport):
        name = f"pulang-{output.stem}.wav"
        rendered = client.render(f"{transport.share_win}\\{name}", start, seconds)
        shutil.move(str(transport.share_wsl / name), output)
        return rendered
    return client.render(str(output.resolve()), start, seconds)


def cmd_stems(args: argparse.Namespace) -> int:
    """
    Bounce each track alone, by soloing it. kaiDAW can only bounce the master.

    Solo is a mix setting and the DAW owns the mix, so each track is put back as
    it was. A soloed track's sends are silenced with everything else, so stems are dry.
    """
    song = load_song(args.song)
    client = _client(args)
    state = _state(args)
    lock = state.load_lock()
    if lock.empty:
        print("Push the song first.", file=sys.stderr)
        return 1
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    seconds = args.seconds or _seconds(song) + 2.0
    rows = []
    for name, info in lock.tracks.items():
        if name == MASTER:
            continue
        client.apply(
            [{"type": "SetTrackState", "trackId": info["id"], "soloed": True}],
            client.revision(),
            "pulang stems: solo",
        )
        try:
            path = out / f"{name}.wav"
            _render_to(client, path, args.start, seconds)
        finally:
            client.apply(
                [{"type": "SetTrackState", "trackId": info["id"], "soloed": False}],
                client.revision(),
                "pulang stems: unsolo",
            )
        samples, rate = analysis.load(str(path))
        rows.append(analysis.measure(samples, rate, name))
    print(analysis.report(rows))
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    path = Path(args.song)
    client = _client(args)
    last = 0.0
    print(f"Watching {path}. Ctrl-C stops.")
    while True:
        modified = path.stat().st_mtime
        if modified != last:
            last = modified
            try:
                result = load_song(path).compile()
                print(push(result.daw, client, _state(args)).summary())
            except (KaidawError, ValueError, KeyError, SyntaxError) as error:
                # A song mid-edit is often broken. Say so and keep watching.
                print(f"error: {error}", file=sys.stderr)
        time.sleep(args.interval)


def _edit_spec(text: str) -> dict:
    """ "[level:]target:field=value", the value read as JSON when it is JSON."""
    place, sep, value = text.partition("=")
    if not sep:
        raise SystemExit(f"error: an edit is target:field=value, not {text!r}")
    parts = place.split(":")
    if len(parts) == 2:
        parts.insert(0, "intent")
    if len(parts) != 3:
        raise SystemExit(f"error: an edit is [level:]target:field=value, not {text!r}")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value
    return {"level": parts[0], "target": parts[1], "field": parts[2], "value": parsed}


def _agent_call(function, **arguments) -> int:
    from pypulang.agent import ToolError, plain

    try:
        result = function(**arguments)
    except ToolError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(result if isinstance(result, str) else json.dumps(plain(result), indent=1))
    return 0


def cmd_variations(args: argparse.Namespace) -> int:
    from pypulang.agent import variations

    found = variations(str(args.song))
    if not found:
        print("No variations.")
    for site, info in found.items():
        print(f"{site}:")
        names = ["source", *(a["name"] for a in info["alternatives"])]
        notes = {a["name"]: a["description"] for a in info["alternatives"]}
        for name in names:
            mark = "*" if info["picked"] == name else " "
            print(f"  {mark} {name}" + (f"  {notes[name]}" if notes.get(name) else ""))
    return 0


def cmd_propose(args: argparse.Namespace) -> int:
    from pypulang.agent import propose

    return _agent_call(
        propose,
        song=str(args.song),
        site=args.site,
        name=args.name,
        edits=[_edit_spec(e) for e in args.edits],
        description=args.description,
        author=args.author,
    )


def cmd_pick(args: argparse.Namespace) -> int:
    from pypulang.agent import pick

    return _agent_call(pick, song=str(args.song), site=args.site, name=args.name)


def cmd_audition(args: argparse.Namespace) -> int:
    from pypulang.agent import audition

    return _agent_call(
        audition, song=str(args.song), site=args.site, out_dir=args.output, port=args.port
    )


def cmd_agent(args: argparse.Namespace) -> int:
    from pypulang.agent import TOOLS

    if args.tool not in TOOLS:
        print(f"error: no tool {args.tool!r}; tools are {', '.join(TOOLS)}", file=sys.stderr)
        return 1
    arguments = json.loads(args.arguments) if args.arguments else {}
    return _agent_call(TOOLS[args.tool], **arguments)


def cmd_mcp(args: argparse.Namespace) -> int:
    from pypulang.mcp import serve

    serve()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pulang", description="Compile music.")
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name: str, handler, help_text: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("song", help="A .py song, or a text file of intent IR")
        sub.set_defaults(handler=handler)
        return sub

    def with_port(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument("--port", type=int, default=DEFAULT_PORT, help="kaiDAW's port")
        return sub

    ir = command("ir", cmd_ir, "Print the IR at a stage")
    ir.add_argument("--stage", choices=STAGES, default="intent")
    ir.add_argument("--locations", action="store_true", help="Include source locations")

    command("check", cmd_check, "Read through the music for likely mistakes")

    trace = command("trace", cmd_trace, "Write the IR after every pass")
    trace.add_argument("-o", "--output", default="build")

    midi = command("midi", cmd_midi, "Write a MIDI file")
    midi.add_argument("-o", "--output", required=True)

    push_cmd = with_port(command("push", cmd_push, "Make kaiDAW hold the song"))
    push_cmd.add_argument("--fresh", action="store_true", help="Build it from nothing here")

    with_port(command("status", cmd_status, "Say what a push would do"))
    with_port(command("pull", cmd_pull, "Keep edits made in the DAW"))
    save = with_port(command("save", cmd_save, "Save the open project"))
    save.add_argument("path", help="A project directory the server can write")
    command("edits", cmd_edits, "List edits made in the DAW")
    serve_cmd = with_port(
        command("serve", cmd_serve, "Show the IR beside kaiDAW, and edit it there")
    )
    serve_cmd.add_argument("--listen", type=int, default=8950, help="This page's port")
    serve_cmd.add_argument(
        "--offline", action="store_true", help="Edit the song without pushing to kaiDAW"
    )
    drop = command("drop", cmd_drop, "Forget one edit")
    drop.add_argument("location")

    render = with_port(command("render", cmd_render, "Push, then bounce to a WAV"))
    render.add_argument("-o", "--output", required=True)
    render.add_argument("--tail", type=float, default=2.0, help="Seconds of release to keep")
    render.add_argument("--fresh", action="store_true", help="Build it from nothing here")

    stems = with_port(command("stems", cmd_stems, "Bounce each track alone"))
    stems.add_argument("-o", "--output", required=True)
    stems.add_argument("--start", type=float, default=0.0, help="Seconds to start from")
    stems.add_argument("--seconds", type=float, default=0.0, help="Length (default: all of it)")

    watch = with_port(command("watch", cmd_watch, "Push every time the file is saved"))
    watch.add_argument("--interval", type=float, default=0.5)

    command("variations", cmd_variations, "List each site's alternatives and which is picked")
    propose_cmd = command("propose", cmd_propose, "Keep an alternative at a site, unpicked")
    propose_cmd.add_argument("site", help='Such as "chorus hook"')
    propose_cmd.add_argument("name", help="The alternative's name")
    propose_cmd.add_argument("edits", nargs="+", help="[level:]target:field=value, one or more")
    propose_cmd.add_argument("--description", default="")
    propose_cmd.add_argument("--author", default="")
    pick_cmd = command("pick", cmd_pick, "Choose an alternative at a site")
    pick_cmd.add_argument("site")
    pick_cmd.add_argument("name", help='An alternative, or "source"')
    audition_cmd = with_port(
        command("audition", cmd_audition, "Render every alternative at a site, for comparing")
    )
    audition_cmd.add_argument("site")
    audition_cmd.add_argument("-o", "--output", required=True, help="A folder for the WAVs")

    agent_cmd = commands.add_parser("agent", help="Run one agent tool: JSON in, JSON out")
    agent_cmd.add_argument(
        "tool", help="describe, ir, review, variations, edit, drop, propose, pick, ..."
    )
    agent_cmd.add_argument("arguments", nargs="?", help='Its arguments as JSON, {"song": ...}')
    agent_cmd.set_defaults(handler=cmd_agent)
    mcp_cmd = commands.add_parser("mcp", help="Serve the agent tools over MCP on stdio")
    mcp_cmd.set_defaults(handler=cmd_mcp)

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except KaidawError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    except BrokenPipeError:
        # `pulang ir song.py | head` closes the pipe early, which is not an error.
        sys.stderr.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
