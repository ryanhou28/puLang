"""
Audio in songs: files on tracks, and samples on a sampler's keys.

The promise under test is the one notes keep: a push makes the DAW hold what the
source says, a second push of the same song changes nothing, and an audio clip
moved or deleted in the DAW stays that way.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

from pypulang import IV, I, Role, piece, root_quarters
from pypulang.backends.kaidaw import KaidawClient, KaidawError, SongState, push
from pypulang.compiler import compile_piece
from pypulang.compiler.dialects import daw
from pypulang.sounds import sampler
from tests.fake_kaidaw import FakeKaidaw


def write_wav(path: Path, hz: float, seconds: float) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        frames = int(44100 * seconds)
        w.writeframes(
            b"".join(
                struct.pack("<h", int(12000 * math.sin(2 * math.pi * hz * k / 44100)))
                for k in range(frames)
            )
        )
    return path


@pytest.fixture
def song_dir(tmp_path) -> Path:
    write_wav(tmp_path / "chop.wav", 440, 0.5)
    write_wav(tmp_path / "riser.wav", 220, 2.0)
    write_wav(tmp_path / "kick.wav", 55, 0.3)
    write_wav(tmp_path / "snare.wav", 180, 0.2)
    return tmp_path


def song(gain: float = 0.0, chop_at: float = 1, kick: str = "kick.wav"):
    with piece(tempo=120, key="C major", title="audio") as p:
        verse = p.section("verse", bars=2)
        verse.harmony(I, IV)
        verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
        verse.audio("vox", "chop.wav", at=chop_at, length=1 / 4, gain_db=gain)
        verse.audio("fx", "riser.wav")
        p.rack("drums", sampler("kit", {36: kick, 38: "snare.wav"}))
        verse.track("drums", role=Role.RHYTHM).notes([(36, 1 / 4), (38, 1 / 4)] * 4)
        p.form([verse, verse])
    return compile_piece(p.to_ir()).daw


def project_of(module) -> daw.ProjectOp:
    return next(op for op in module.body.block.ops if isinstance(op, daw.ProjectOp))


@pytest.fixture
def connected(song_dir):
    fake = FakeKaidaw()
    return KaidawClient(transport=fake), fake, SongState(song_dir / "song.pulang")


def audio_clips(client):
    return {c["name"]: c for c in client.projection("detail")["clips"] if c.get("kind") == "audio"}


class TestLowering:
    def test_a_file_in_a_section_is_one_clip_per_occurrence(self):
        project = project_of(song())
        vox = next(t for t in project.tracks() if t.track.data == "vox")
        clips = {c.key.data: c for c in vox.audio_clips()}
        assert set(clips) == {"verse#1/vox/audio0", "verse#2/vox/audio0"}
        first = clips["verse#1/vox/audio0"]
        assert first.start.value.data == 3840 and first.length.value.data == 960
        assert first.file.data == "chop.wav"

    def test_a_file_with_no_length_plays_to_its_end(self):
        fx = next(t for t in project_of(song()).tracks() if t.track.data == "fx")
        assert all(c.length is None for c in fx.audio_clips())

    def test_a_sampler_carries_its_sounds(self):
        drums = next(t for t in project_of(song()).tracks() if t.track.data == "drums")
        kit = drums.plugins()[0]
        assert kit.identifier.data == "sampler"
        sounds = kit.sound_list()
        assert [(s["file"], s["root"], s["low"], s["high"], s["one_shot"]) for s in sounds] == [
            ("kick.wav", 36, 36, 36, True),
            ("snare.wav", 38, 38, 38, True),
        ]


class TestPush:
    def test_audio_reaches_the_daw_and_each_file_is_imported_once(self, connected):
        client, fake, state = connected
        push(song(), client, state)
        clips = audio_clips(client)
        assert set(clips) == {
            "verse#1/vox/audio0",
            "verse#2/vox/audio0",
            "verse#1/fx/audio1",
            "verse#2/fx/audio1",
        }
        # The riser plays to its end: two seconds at 120 bpm is a bar
        assert clips["verse#1/fx/audio1"]["length"] == 3840
        assert fake.uploads == 4  # chop, riser, kick, snare

    def test_a_second_push_changes_nothing_and_sends_nothing(self, connected):
        client, fake, state = connected
        push(song(), client, state)
        report = push(song(), client, state)
        assert report.operations == 0
        assert fake.uploads == 4

    def test_a_gain_change_in_the_source_reaches_the_clip(self, connected):
        client, _, state = connected
        push(song(), client, state)
        push(song(gain=-6), client, state)
        assert all(c["gainDb"] == -6 for name, c in audio_clips(client).items() if "/vox/" in name)

    def test_a_clip_moved_in_the_daw_stays_moved(self, connected):
        client, _, state = connected
        push(song(), client, state)
        clip = audio_clips(client)["verse#1/vox/audio0"]
        client.apply(
            [{"type": "MoveClip", "clipId": clip["id"], "start": 4800}],
            client.revision(),
            "by hand",
        )
        push(song(gain=-3), client, state)
        assert audio_clips(client)["verse#1/vox/audio0"]["start"] == 4800

    def test_a_clip_deleted_in_the_daw_stays_deleted(self, connected):
        client, _, state = connected
        push(song(), client, state)
        clip = audio_clips(client)["verse#2/fx/audio1"]
        client.apply([{"type": "DeleteClip", "clipId": clip["id"]}], client.revision(), "by hand")
        push(song(), client, state)
        assert "verse#2/fx/audio1" not in audio_clips(client)

    def test_the_sampler_gets_its_sounds_and_keeps_them(self, connected):
        client, _, state = connected
        push(song(), client, state)
        kit = next(p for p in client.projection()["plugins"] if p.get("sounds"))
        assert [(s["rootNote"], s["openEnded"]) for s in kit["sounds"]] == [(36, True), (38, True)]
        push(song(kick="snare.wav"), client, state)
        kit = next(p for p in client.projection()["plugins"] if p.get("sounds"))
        assert kit["sounds"][0]["assetId"] == kit["sounds"][1]["assetId"]

    def test_a_missing_file_is_named(self, connected, song_dir):
        client, _, state = connected
        (song_dir / "chop.wav").unlink()
        with pytest.raises(KaidawError, match="chop.wav"):
            push(song(), client, state)
