"""
Asking an agent from the companion page.

The agent is Claude Code (`claude -p`) with `pulang mcp` as its only MCP server
and Read as its only built-in tool: it reads the song and puLang's docs, and
changes the song only through puLang's tools, each checked by compiling. By
default it proposes alternatives for the person to hear in kaiDAW and pick;
asked to, it makes the change. It runs with the person's own Claude Code login,
so each request uses their plan.

Not `render` or `audition`: those push to kaiDAW, which the person is listening
to, and the agent cannot hear the result anyway.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pypulang.backends.kaidaw.state import SongState

TOOLS = (
    "describe",
    "ir",
    "review",
    "variations",
    "edit",
    "drop",
    "propose",
    "pick",
    "drop_variation",
    "readings",
    "keep_reading",
    "fold",
)

MODES = {
    "propose": (
        "Propose alternatives with the propose tool instead of changing the song: one to "
        'three variations at one site named for what they change (such as "chorus hook" or '
        '"verse harmony"), each with a description of what it does musically. Do not pick '
        "one: the person hears each in kaiDAW and picks."
    ),
    "edit": (
        "Make the change with the edit tool. The person hears it at once and can drop any "
        "edit, or fold the edits into the source, from the companion page."
    ),
}

DOCS = Path(__file__).resolve().parent.parent / "docs"


@dataclass
class Run:
    """One request: what was asked, what the agent did, and what it said."""

    prompt: str
    mode: str
    started: float = field(default_factory=time.time)
    status: str = "running"  # running, done, failed, stopped
    steps: list[str] = field(default_factory=list)
    answer: str = ""
    finished: float | None = None
    proposed: list[tuple[str, str]] = field(default_factory=list)  # (site, variation)
    edited: list[str] = field(default_factory=list)  # edit keys it made
    handled: bool = False  # finished, and the page has taken in what it left
    process: subprocess.Popen | None = field(default=None, repr=False)

    @property
    def seconds(self) -> float:
        return (self.finished or time.time()) - self.started


def instructions(song: Path, mode: str) -> str:
    docs = DOCS / "compiler.md"
    reading = (
        f"Before changing anything, read the song file and {docs} (at least its sections "
        '"Editing above the notes", "Variations" and "Agent tools"), and call describe.'
        if docs.exists()
        else "Before changing anything, read the song file and call describe."
    )
    return (
        "You are helping a person change a song while they listen to it in kaiDAW, a DAW. "
        f"The song is the puLang file {song}, a Python file in puLang's language. {reading} "
        f'Change the song only through the pulang tools, passing song="{song}" to each; '
        f"never write files. {MODES[mode]} The person sees only your final answer and what "
        "the tools leave in the song: keep the answer to a few plain sentences saying what "
        "changed, or what each alternative does, and where to listen, by section and bar."
    )


def command(song: Path, prompt: str, mode: str, claude: str) -> list[str]:
    """The `claude` command for one request."""
    pulang = shutil.which("pulang") or str(Path(sys.executable).with_name("pulang"))
    servers = {"mcpServers": {"pulang": {"command": pulang, "args": ["mcp"]}}}
    cmd = [
        claude,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--strict-mcp-config",
        "--mcp-config",
        json.dumps(servers),
        "--tools",
        "Read",
        "--allowedTools",
        " ".join(["Read", *(f"mcp__pulang__{t}" for t in TOOLS)]),
        "--append-system-prompt",
        instructions(song, mode),
    ]
    if DOCS.exists():
        cmd += ["--add-dir", str(DOCS)]
    return cmd


def environment() -> dict[str, str]:
    """
    The environment for the agent: this one without what marks a process as part
    of a Claude Code session, so a page started from one still starts a fresh agent.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC_"))}


def steps_of(event: dict[str, Any]) -> list[str]:
    """What one line of the agent's stream says it did, for the page."""
    out: list[str] = []
    if event.get("type") == "assistant":
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                out.append(_tool_step(block.get("name", ""), block.get("input", {})))
            elif block.get("type") == "text" and block.get("text", "").strip():
                out.append(block["text"].strip())
    elif event.get("type") == "user":
        for block in event.get("message", {}).get("content", []):
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and block.get("is_error")
            ):
                content = block.get("content")
                text = content if isinstance(content, str) else json.dumps(content)
                out.append(f"↳ refused: {text[:240]}")
    return out


def _tool_step(name: str, args: dict[str, Any]) -> str:
    tool = name.removeprefix("mcp__pulang__")
    if tool == "Read":
        return f"read {Path(str(args.get('file_path', ''))).name}"
    if tool == "edit":
        return f"edit {args.get('target')} {args.get('field')} = {args.get('value')}"
    if tool == "propose":
        count = len(args.get("edits", []))
        return f'propose {args.get("name")} at "{args.get("site")}" ({count} edit(s))'
    if tool == "pick":
        return f'pick {args.get("name")} at "{args.get("site")}"'
    detail = [str(args[k]) for k in ("stage", "section", "key", "name") if args.get(k)]
    return " ".join([tool, *detail])


class Agent:
    """Runs requests one at a time for one song, keeping each run for the page."""

    def __init__(
        self,
        song: Path,
        claude: str | None = None,
        on_done: Callable[[Run], None] | None = None,
    ):
        self.song = song.resolve()
        # PULANG_CLAUDE names another command, such as a stand-in for tests
        self.claude = claude or os.environ.get("PULANG_CLAUDE") or shutil.which("claude")
        self.on_done = on_done
        self.runs: list[Run] = []
        self.lock = threading.Lock()

    @property
    def available(self) -> bool:
        return bool(self.claude)

    @property
    def running(self) -> Run | None:
        return next((r for r in self.runs if not r.handled), None)

    def ask(self, prompt: str, mode: str = "propose") -> Run:
        if not self.claude:
            raise ValueError("Claude Code (`claude`) is not installed where this page runs")
        if mode not in MODES:
            raise ValueError(f"No mode {mode!r}; there are {', '.join(MODES)}")
        if not prompt.strip():
            raise ValueError("Say what you want changed")
        with self.lock:
            if self.running is not None:
                raise ValueError("The agent is still working on the last request")
            run = Run(prompt.strip(), mode)
            before = self._kept()
            run.process = subprocess.Popen(
                command(self.song, run.prompt, mode, self.claude),
                cwd=self.song.parent,
                env=environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.runs.insert(0, run)
        threading.Thread(target=self._follow, args=(run, before), daemon=True).start()
        return run

    def stop(self) -> None:
        run = self.running
        if run is not None and run.process is not None:
            run.status = "stopped"
            run.process.terminate()

    def _follow(self, run: Run, before: tuple[set[str], set[tuple[str, str]]]) -> None:
        assert run.process is not None and run.process.stdout is not None
        outcome = None
        for line in run.process.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            run.steps.extend(steps_of(event))
            if event.get("type") == "result":
                run.answer = str(event.get("result") or "")
                outcome = "failed" if event.get("is_error") else "done"
        run.process.wait()
        if outcome is None:
            error = run.process.stderr.read().strip() if run.process.stderr else ""
            run.answer = (
                run.answer or error[-600:] or f"claude exited with {run.process.returncode}"
            )
        # What it left in the song, before the run counts as finished
        edits, variations = self._kept()
        run.edited = sorted(edits - before[0])
        run.proposed = sorted(variations - before[1])
        run.finished = time.time()
        if run.status == "running":
            run.status = outcome or "failed"
        try:
            if self.on_done is not None:
                self.on_done(run)
        finally:
            run.handled = True

    def _kept(self) -> tuple[set[str], set[tuple[str, str]]]:
        """The song's edit keys and (site, variation) pairs, to tell what a run added."""
        overrides = SongState.beside(self.song).load_overrides()
        edits = {f"{e['level']}:{e['target']}:{e['field']}" for e in overrides.edits}
        variations = {(v.get("site", ""), name) for name, v in overrides.variations.items()}
        return edits, variations
