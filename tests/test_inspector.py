"""
Edits above the notes, the IR inspector, and lifting hand edits back up.

The promise under test: an edit made at a level stays at that level and reaches
every note it should and no other, and a hand edit in the DAW can be read as the
higher edit it means, checked by lowering it.
"""

from __future__ import annotations

import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import pytest

from pypulang import lift
from pypulang.backends.kaidaw import KaidawClient, SongState, pull, push
from pypulang.compiler.dialects import score
from pypulang.compiler.edits import Edit
from pypulang.inspector import Model, voiced_module
from pypulang.lift import daw_notes
from pypulang.serve import Companion, _Handler
from pypulang.songfile import load_song
from tests.fake_kaidaw import FakeKaidaw

SONG = """
from pypulang import *

with piece(tempo=120, key="C major", title="tiny") as song:
    a = song.section("a", bars=2)
    a.chart("Dm7 G7 | Cmaj7")
    a.track("keys", role=Role.HARMONY).pattern(comp).voicing("rootless", 52, 72)
    a.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
    a.track("lead", role=Role.MELODY).line("a5/2 g5 | e5/1")
    song.form([a, a])
"""


@pytest.fixture
def song_file(tmp_path):
    path = tmp_path / "tiny.py"
    path.write_text(SONG)
    return path


@pytest.fixture
def connected(song_file):
    client = KaidawClient(transport=FakeKaidaw())
    state = SongState.beside(song_file)
    push(load_song(song_file).compile().daw, client, state, fresh=True)
    return client, state


def slots(result, tag: str, part: str) -> list[score.SlotOp]:
    top = next(o for o in voiced_module(result).body.block.ops if isinstance(o, score.ScoreOp))
    found = next(p for p in top.parts() if p.part.data == part)
    return [s for s in found.slots() if s.section.data == tag]


def bass_notes(result, tag: str) -> list[int]:
    return [
        n[0] for loc, n in sorted(daw_notes(result.daw).items()) if loc.startswith(f"{tag}/bass/")
    ]


class TestEdits:
    def test_an_intent_chord_edit_changes_every_occurrence(self, song_file):
        song = load_song(song_file)
        edit = Edit("intent", "a/harmony@1+2", "chord", "Db7", "G7")
        result = song.compile(keep_trace=True, edits=[edit])
        for tag in ("a#1", "a#2"):
            assert slots(result, tag, "keys")[1].chord.data.numeral == "II"
        assert result.edits.applied == [edit.key]

    def test_a_score_chord_edit_changes_one_occurrence_and_the_bass_follows(self, song_file):
        song = load_song(song_file)
        plain = song.compile(edits=[])
        edited = song.compile(edits=[Edit("score", "a#2/harmony@1+2", "chord", "Db7", "G7")])
        assert bass_notes(edited, "a#1") == bass_notes(plain, "a#1")
        assert bass_notes(edited, "a#2") != bass_notes(plain, "a#2")
        # The bass plays the new root, D flat, where it played G
        assert any(p % 12 == 1 for p in bass_notes(edited, "a#2"))

    def test_an_exact_voicing_is_kept_after_voice_leading(self, song_file):
        song = load_song(song_file)
        edit = Edit("score", "a#1/keys/c0", "pitches", [62, 65, 69, 72], [60, 65, 69])
        result = song.compile(keep_trace=True, edits=[edit])
        assert slots(result, "a#1", "keys")[0].pitch_list() == [62, 65, 69, 72]
        assert slots(result, "a#2", "keys")[0].pitch_list() == [60, 65, 69]

    def test_track_settings(self, song_file):
        song = load_song(song_file)
        plain = daw_notes(song.compile(edits=[]).daw)
        up = daw_notes(song.compile(edits=[Edit("intent", "a/lead", "octave", 1, 0)]).daw)
        lead = [loc for loc in plain if "/lead/" in loc]
        assert all(up[loc][0] == plain[loc][0] + 12 for loc in lead)
        muted = daw_notes(song.compile(edits=[Edit("intent", "a/bass", "muted", True, False)]).daw)
        assert not any("/bass/" in loc for loc in muted)

    def test_a_stale_edit_still_applies_and_says_so(self, song_file):
        song = load_song(song_file)
        edit = Edit("intent", "a/harmony@1+2", "chord", "Db7", "G13")  # made when it was G13
        result = song.compile(edits=[edit])
        assert result.edits.applied == [edit.key]
        assert any("source now gives 'G7'" in line for line in result.warnings)

    def test_an_edit_whose_place_is_gone_is_orphaned(self, song_file):
        result = load_song(song_file).compile(
            edits=[Edit("intent", "a/harmony@2+2", "chord", "F", "C")]
        )
        assert result.edits.orphaned and not result.edits.applied

    def test_a_song_compiles_with_the_edits_kept_beside_it(self, song_file):
        state = SongState.beside(song_file)
        overrides = state.load_overrides()
        overrides.put_edit(Edit("intent", "a/lead", "octave", 1, 0))
        state.save_overrides(overrides)
        assert load_song(song_file).compile().edits.applied == ["intent:a/lead:octave"]


class TestInspector:
    def test_a_note_is_traced_up_every_level(self, song_file, connected):
        client, state = connected
        model = Model(
            load_song(song_file).compile(keep_trace=True), state.load_lock(), state.load_overrides()
        )
        clip_id = state.load_lock().clips["a#2/keys"]["id"]
        clip = next(c for c in client.projection()["clips"] if c["id"] == clip_id)
        view = model.clip(clip_id, [clip["notes"][0]["id"]])
        chain = view.notes[0]
        assert chain.tag == "a#2" and chain.track == "keys"
        assert chain.daw is not None and chain.event is not None and chain.score is not None
        assert chain.slot.target == "a#2/keys/c0" and chain.chord.symbol == "Dm7"
        assert [c.symbol for c in view.chords] == ["Dm7", "G7", "Cmaj7"]
        assert view.track_info.settings["voicing"] == "rootless(52,72)"


class TestCompanion:
    def test_an_edit_reaches_the_daw_and_dropping_it_undoes_it(self, song_file, connected):
        client, state = connected
        companion = Companion(song_file, client)
        clip_id = state.load_lock().clips["a#1/lead"]["id"]

        def lead():
            clip = next(c for c in client.projection()["clips"] if c["id"] == clip_id)
            return sorted(n["pitch"] for n in clip["notes"])

        before = lead()
        message = companion.edit("intent", "a/lead", "octave", "1")
        assert "pushed" in message
        assert lead() == [p + 12 for p in before]
        companion.drop("intent:a/lead:octave")
        assert lead() == before

    def test_an_unreadable_value_is_refused(self, song_file, connected):
        companion = Companion(song_file, connected[0])
        with pytest.raises(ValueError):
            companion.edit("intent", "a/harmony@1+0", "chord", "H#q")

    def test_the_page_serves_and_an_edit_redirects_back(self, song_file, connected):
        client, state = connected
        handler = type("H", (_Handler,), {"companion": Companion(song_file, client)})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            clip_id = state.load_lock().clips["a#1/keys"]["id"]
            page = urllib.request.urlopen(f"{base}/inspect?clipId={clip_id}").read().decode()
            assert "a#1" in page and "rootless(52,72)" in page and "Cmaj7" in page
            form = urlencode(
                {
                    "level": "intent",
                    "target": "a/keys",
                    "field": "velocity",
                    "value": "90",
                    "back": "/inspect",
                }
            ).encode()
            response = urllib.request.urlopen(urllib.request.Request(f"{base}/edit", data=form))
            assert response.status == 200  # followed the 303 back to the page
            assert "intent:a/keys:velocity" in response.read().decode()
        finally:
            server.shutdown()


class TestLift:
    def hand_edit(self, client, state, clip_key, change):
        clip_id = state.load_lock().clips[clip_key]["id"]
        clip = next(c for c in client.projection()["clips"] if c["id"] == clip_id)
        notes = [change(dict(n)) for n in clip["notes"]]
        client.apply(
            [{"type": "UpsertNotes", "clipId": clip_id, "notes": [n for n in notes if n]}],
            client.revision(),
            "by hand",
        )
        pull(client, state)

    def suggestions(self, song_file, state, clip_key):
        song = load_song(song_file)
        model = Model(song.compile(keep_trace=True), state.load_lock(), state.load_overrides())
        return song, lift.suggest(song, model, clip_key)

    def test_a_part_moved_up_an_octave_reads_as_an_octave_edit(self, song_file, connected):
        client, state = connected
        self.hand_edit(client, state, "a#1/lead", lambda n: dict(n, pitch=n["pitch"] + 12))
        _, found = self.suggestions(song_file, state, "a#1/lead")
        octave = next(s for s in found if s.edits[0].field == "octave")
        assert octave.edits[0].value == 1
        assert len(octave.explains) == octave.in_scope == 3
        # It is an intent edit, so the other occurrence moves too, and it says so
        assert octave.disturbs == 3

    def test_a_respelled_chord_reads_as_that_chord_keeping_the_notes(self, song_file, connected):
        client, state = connected
        # G7's D moved to A flat: B F A flat is a rootless D flat 7, the tritone sub
        self.hand_edit(
            client,
            state,
            "a#1/keys",
            lambda n: dict(n, pitch=68) if 1920 <= n["start"] < 3840 and n["pitch"] == 62 else None,
        )
        song, found = self.suggestions(song_file, state, "a#1/keys")
        chord = next(
            s for s in found if s.edits[0].field == "chord" and s.edits[0].level == "score"
        )
        assert chord.edits[0].value == "Db7" and chord.edits[1].field == "pitches"
        assert len(chord.explains) == chord.in_scope
        overrides = lift.accept(song, state.load_overrides(), chord)
        assert not overrides.notes  # the note edit is explained, so it goes
        result = song.compile(edits=overrides.edit_list())
        assert not result.edits.stale
        # The bass now plays the tritone sub's root in a#1
        assert any(p % 12 == 1 for p in bass_notes(result, "a#1"))

    def test_edits_no_reading_explains_stay_note_edits(self, song_file, connected):
        client, state = connected
        first = {}

        def nudge(n):
            if not first:
                first.update(n)
                return dict(n, start=n["start"] + 10)
            return None

        self.hand_edit(client, state, "a#1/lead", nudge)
        _, found = self.suggestions(song_file, state, "a#1/lead")
        assert found == []
