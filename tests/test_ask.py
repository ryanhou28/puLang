"""
Asking an agent from the companion page: the command it runs, what the page
shows of its stream, and what it left in the song.
"""

from __future__ import annotations

import json
import stat
import sys
import time

import pytest

from pypulang.ask import TOOLS, Agent, command, environment, steps_of
from pypulang.serve import Companion

SONG = """
from pypulang import *

with piece(tempo=80, key="F minor", title="ask") as song:
    song.motif("m", "5/4 6 5 3")
    a = song.section("a", bars=2)
    a.chart("Fm9 | Bbm7 Eb7")
    a.track("lead", role=Role.MELODY).melody("m; m -1", low=60, high=76)
    song.form([a])
"""

# Stands in for `claude -p`: proposes a variation through puLang's own tool, then
# streams what the real one would.
FAKE = """#!{python}
import json, os, sys
from pypulang import agent
agent.propose(os.environ["FAKE_SONG"], "lead line", "lower", [
    {{"target": "a/lead", "field": "melody", "value": "m; m -2"}}], "a step lower")
for event in [
    {{"type": "system", "subtype": "init"}},
    {{"type": "assistant", "message": {{"content": [
        {{"type": "tool_use", "name": "mcp__pulang__describe", "input": {{"song": "x"}}}}]}}}},
    {{"type": "user", "message": {{"content": [
        {{"type": "tool_result", "is_error": True, "content": "No section 'z'"}}]}}}},
    {{"type": "assistant", "message": {{"content": [
        {{"type": "tool_use", "name": "mcp__pulang__propose",
          "input": {{"site": "lead line", "name": "lower", "edits": [{{}}]}}}}]}}}},
    {{"type": "result", "result": "One alternative at lead line: a step lower.", "is_error": False}},
]:
    print(json.dumps(event), flush=True)
"""


@pytest.fixture
def song(tmp_path, monkeypatch):
    path = tmp_path / "ask.py"
    path.write_text(SONG)
    fake = tmp_path / "claude"
    fake.write_text(FAKE.format(python=sys.executable))
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("FAKE_SONG", str(path))
    return path


def wait(agent):
    for _ in range(200):
        if agent.running is None:
            return agent.runs[0]
        time.sleep(0.05)
    raise AssertionError("the agent never finished")


def test_the_agent_gets_puLangs_tools_and_reading_only(tmp_path):
    cmd = command(tmp_path / "s.py", "a darker chorus", "propose", "claude")
    allowed = cmd[cmd.index("--allowedTools") + 1].split()
    assert cmd[cmd.index("--tools") + 1] == "Read" and "--strict-mcp-config" in cmd
    assert "mcp__pulang__propose" in allowed and len(allowed) == len(TOOLS) + 1
    assert not any(t in allowed for t in ("mcp__pulang__render", "mcp__pulang__audition"))
    servers = json.loads(cmd[cmd.index("--mcp-config") + 1])["mcpServers"]
    assert servers["pulang"]["args"] == ["mcp"]
    assert "propose tool" in cmd[cmd.index("--append-system-prompt") + 1]


def test_a_page_started_from_a_claude_session_still_starts_a_fresh_agent(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "x")
    found = environment()
    assert "CLAUDECODE" not in found and "CLAUDE_CODE_SESSION_ID" not in found and "PATH" in found


def test_a_run_shows_its_steps_its_answer_and_what_it_proposed(song):
    done = []
    agent = Agent(song, claude=str(song.parent / "claude"), on_done=done.append)
    agent.ask("a lower line")
    run = wait(agent)
    assert run.status == "done" and run.answer.startswith("One alternative")
    assert run.steps == [
        "describe",
        "↳ refused: No section 'z'",
        'propose lower at "lead line" (1 edit(s))',
    ]
    assert run.proposed == [("lead line", "lower")] and run.edited == []
    assert done == [run]


def test_one_request_at_a_time(song):
    agent = Agent(song, claude=str(song.parent / "claude"))
    agent.ask("first")
    with pytest.raises(ValueError, match="still working"):
        agent.ask("second")
    wait(agent)


def test_the_page_lists_the_runs_and_offers_the_proposals(song):
    companion = Companion(song, None)
    companion.agent.claude = str(song.parent / "claude")
    assert 'id="tab-agent"' in companion.page({}) and 'name="prompt"' in companion.page({})
    companion.ask("a lower line", "propose")
    wait(companion.agent)
    shown = companion.runs("/")
    assert "a lower line" in shown and "pick and hear it" in shown and "data-running" not in shown
    assert "proposed 1 alternative" in companion.message


def test_a_tool_error_is_a_step():
    event = {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "is_error": True,
                    "content": [{"type": "text", "text": "bad"}],
                }
            ]
        },
    }
    assert steps_of(event)[0].startswith("↳ refused:")
