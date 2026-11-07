"""The pulang command, end to end, on a small song."""

from __future__ import annotations

import os
import time

import mido
import pytest

from pypulang.backends.kaidaw import KaidawClient, SongState
from pypulang.cli import main
from tests.fake_kaidaw import FakeKaidaw

SONG = """
from pypulang import *
from pypulang.compiler.passes.perform import Swing

with piece(tempo=120, key="C major", title="cli") as p:
    a = p.section("a", bars=2)
    a.chart("Dm7 G7 | Cmaj7")
    a.track("bass", role=Role.BASS).pattern(walking_bass)
    a.track("keys", role=Role.HARMONY).pattern(comp).voicing("rootless", 52, 72)

pipeline = {"event": [Swing(tracks=("keys",))]}
"""


@pytest.fixture
def song(tmp_path):
    path = tmp_path / "song.py"
    path.write_text(SONG)
    return path


@pytest.fixture
def fake(monkeypatch):
    server = FakeKaidaw()
    monkeypatch.setattr("pypulang.cli._client", lambda args: KaidawClient(transport=server))
    return server


@pytest.mark.parametrize("stage", ["intent", "score", "event", "daw"])
def test_ir_prints_each_stage(song, capsys, stage):
    assert main(["ir", str(song), "--stage", stage]) == 0
    assert f"{stage}." in capsys.readouterr().out


def test_hand_written_ir_compiles(song, tmp_path, capsys):
    main(["ir", str(song), "--stage", "intent"])
    written = tmp_path / "song.mlir"
    written.write_text(capsys.readouterr().out)
    assert main(["ir", str(written), "--stage", "daw"]) == 0
    assert "daw.project" in capsys.readouterr().out


def test_midi_writes_a_file(song, tmp_path):
    out = tmp_path / "song.mid"
    assert main(["midi", str(song), "-o", str(out)]) == 0
    assert any(m.type == "note_on" for t in mido.MidiFile(out).tracks for m in t)


def test_trace_writes_the_ir_after_every_pass(song, tmp_path):
    out = tmp_path / "trace"
    assert main(["trace", str(song), "-o", str(out)]) == 0
    names = {p.name for p in out.iterdir()}
    assert {"intent.mlir", "daw.mlir", "01-voice-lead.mlir"} <= names
    assert any("swing" in n for n in names)


def test_check_reports_on_the_music(song, capsys):
    assert main(["check", str(song)]) == 0
    assert "Strong-beat melody notes" in capsys.readouterr().out


def test_push_status_pull_edits_drop(song, fake, capsys):
    assert main(["push", str(song)]) == 0
    assert "tracks" in capsys.readouterr().out
    assert main(["status", str(song)]) == 0
    assert "0 operations" in capsys.readouterr().out

    state = SongState.beside(song)
    lock = state.load_lock()
    location, entry = next(iter(lock.notes.items()))
    clip = lock.clips[entry["clip"]]["id"]
    fake.request(
        "POST",
        "/apply",
        {
            "baseRevision": fake.revision,
            "operations": [{"type": "DeleteNotes", "clipId": clip, "noteIds": [entry["id"]]}],
        },
    )

    assert main(["pull", str(song)]) == 0
    assert "Captured 1" in capsys.readouterr().out
    assert main(["edits", str(song)]) == 0
    assert location in capsys.readouterr().out
    assert main(["drop", str(song), location]) == 0
    capsys.readouterr()
    assert main(["edits", str(song)]) == 0
    assert "No edits" in capsys.readouterr().out


def test_watch_pushes_and_survives_a_broken_save(song, fake, monkeypatch, capsys):
    saves = iter(["broken ( python", SONG, None])

    def next_save(_seconds):
        text = next(saves)
        if text is None:
            raise KeyboardInterrupt
        song.write_text(text)
        os.utime(song, (time.time() + 10 + fake.revision, time.time() + 10 + fake.revision))

    monkeypatch.setattr("pypulang.cli.time.sleep", next_save)
    assert main(["watch", str(song)]) == 0
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "operations" in captured.out


def test_dropping_an_unknown_edit_says_so(song, capsys):
    assert main(["drop", str(song), "nowhere"]) == 1
    assert "No edit at" in capsys.readouterr().err


def test_a_broken_song_names_what_is_wrong(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("x = 1\n")
    with pytest.raises(ValueError, match="expected one piece"):
        main(["ir", str(bad)])
