"""
Hand edits to a melody, read back as edits of its motifs or its phrase.

The promise under test: notes dragged in the DAW's piano roll come back as the
higher edit they mean, a motif rewritten everywhere it is used or one statement of
it moved, and every reading is checked by lowering the song with it.
"""

from __future__ import annotations

import pytest

from pypulang import lift
from pypulang.backends.kaidaw import KaidawClient, SongState, pull, push
from pypulang.inspector import Model
from pypulang.lift import daw_notes
from pypulang.songfile import load_song
from tests.fake_kaidaw import FakeKaidaw

SONG = """
from pypulang import *

with piece(tempo=120, key="C major", title="lines") as song:
    song.motif("m", "1/4 2 3 5")
    a = song.section("a", bars=2)
    a.chart("Cmaj9 | Dm9")
    a.track("lead", role=Role.MELODY).melody("m; m +1", low=55, high=72)
    b = song.section("b", bars=1)
    b.chart("Cmaj9")
    b.track("lead", role=Role.MELODY).melody("m -1", low=55, high=72)
    song.form([a, b, a])
"""


@pytest.fixture
def song_file(tmp_path):
    path = tmp_path / "lines.py"
    path.write_text(SONG)
    return path


@pytest.fixture
def connected(song_file):
    client = KaidawClient(transport=FakeKaidaw())
    state = SongState.beside(song_file)
    push(load_song(song_file).compile().daw, client, state, fresh=True)
    return client, state


def hand_edit(client, state, clip_key, change):
    clip_id = state.load_lock().clips[clip_key]["id"]
    clip = next(c for c in client.projection()["clips"] if c["id"] == clip_id)
    notes = [change(dict(n)) for n in sorted(clip["notes"], key=lambda n: n["start"])]
    client.apply(
        [{"type": "UpsertNotes", "clipId": clip_id, "notes": [n for n in notes if n]}],
        client.revision(),
        "by hand",
    )
    pull(client, state)


def readings(song_file, state, clip_key):
    song = load_song(song_file)
    model = Model(song.compile(keep_trace=True), state.load_lock(), state.load_overrides())
    return song, lift.suggest(song, model, clip_key)


def lead(song, edits, tag):
    notes = daw_notes(song.compile(edits=edits).daw)
    return [
        n[0]
        for loc, n in sorted(notes.items(), key=lambda kv: kv[1][1])
        if loc.startswith(f"{tag}/lead/")
    ]


def nth(indices, change):
    """Change only the notes at these positions in the clip, in time order."""
    seen = {"i": -1}

    def edit(note):
        seen["i"] += 1
        return change(note) if seen["i"] in indices else None

    return edit


class TestMotifReadings:
    def test_a_changed_note_reads_as_the_motif_rewritten_everywhere(self, song_file, connected):
        client, state = connected
        # The first statement's last note, G, up to A: degree 5 becomes 6
        hand_edit(client, state, "a#1/lead", nth({3}, lambda n: dict(n, pitch=n["pitch"] + 2)))
        song, found = readings(song_file, state, "a#1/lead")
        motif = next(s for s in found if s.edits[0].target == "motif/m")
        assert motif.edits[0].value == "1/4 2 3 6"
        assert motif.explains and motif.disturbs > 0  # the other statements follow
        overrides = lift.accept(song, state.load_overrides(), motif)
        assert not overrides.notes
        assert lead(song, overrides.edit_list(), "b#1") == [59, 60, 62, 67]  # m -1, now B C D G

    def test_the_last_note_alone_also_reads_as_a_new_ending(self, song_file, connected):
        client, state = connected
        hand_edit(client, state, "a#1/lead", nth({3}, lambda n: dict(n, pitch=n["pitch"] + 2)))
        _, found = readings(song_file, state, "a#1/lead")
        ending = next(s for s in found if s.edits[0].field == "melody")
        assert ending.edits[0].value == "m end 6; m +1"
        # It changes the phrase of section a only, so it disturbs less than the motif
        motif = next(s for s in found if s.edits[0].target == "motif/m")
        assert ending.disturbs < motif.disturbs

    def test_a_note_moved_in_time_moves_in_the_motif(self, song_file, connected):
        client, state = connected
        # The third note, E on beat 3, an eighth later and an eighth long
        hand_edit(
            client,
            state,
            "a#1/lead",
            nth({2}, lambda n: dict(n, start=n["start"] + 480, duration=480)),
        )
        _, found = readings(song_file, state, "a#1/lead")
        motif = next(s for s in found if s.edits[0].target == "motif/m")
        assert motif.edits[0].value == "1/4 2 r/8 3 5/4"
        assert motif.explains


class TestPhraseReadings:
    def test_a_whole_statement_moved_reads_as_a_sequence_step(self, song_file, connected):
        client, state = connected
        # The second statement, D E F A, up a step to E F G B
        up = {62: 64, 64: 65, 65: 67, 69: 71}
        hand_edit(
            client, state, "a#1/lead", nth({4, 5, 6, 7}, lambda n: dict(n, pitch=up[n["pitch"]]))
        )
        song, found = readings(song_file, state, "a#1/lead")
        best = found[0]
        assert best.edits[0].field == "melody" and best.edits[0].value == "m; m +2"
        assert len(best.explains) == best.in_scope == 4
        overrides = lift.accept(song, state.load_overrides(), best)
        assert lead(song, overrides.edit_list(), "a#2")[4:] == [64, 65, 67, 71]

    def test_a_statement_moved_an_octave_reads_as_an_octave_up(self, song_file, connected):
        client, state = connected
        hand_edit(
            client, state, "a#1/lead", nth({0, 1, 2, 3}, lambda n: dict(n, pitch=n["pitch"] + 12))
        )
        _, found = readings(song_file, state, "a#1/lead")
        phrase = next(s for s in found if s.edits[0].field == "melody")
        assert phrase.edits[0].value == "m ^; m +1"


class TestRoundTrips:
    def test_motif_text_reads_back_as_it_was_written(self):
        from pypulang.motifs import format_motif, parse_motif

        for text in (
            "5/8 6 1'/4 7/8 5/4. r/8",
            "r/8 5,/8 4, 3,",
            "3/8 3 2 b2 1/4. 6,/8 #7,/4. 1/8 5,/2",
        ):
            motif = parse_motif(text)
            again = parse_motif(format_motif(list(motif.notes), motif.length))
            assert again == motif

    def test_phrases_read_back_as_they_were_written(self):
        from pypulang.motifs import format_phrase, parse_phrase

        for text in (
            "hook; hook -2; hook vary 2; cadence",
            "rest 2; m +2 inv end 1; m first 6 x1/2",
        ):
            assert format_phrase(parse_phrase(text)) == text


class TestAgent:
    def test_an_agent_reads_and_keeps_a_reading(self, song_file, connected):
        from pypulang import agent

        client, state = connected
        up = {62: 64, 64: 65, 65: 67, 69: 71}
        hand_edit(
            client, state, "a#1/lead", nth({4, 5, 6, 7}, lambda n: dict(n, pitch=up[n["pitch"]]))
        )
        found = agent.readings(str(song_file), "a#1/lead", pull_first=False)
        assert found["hand_edits"] == 4
        best = found["readings"][0]
        assert best["edits"][0]["value"] == "m; m +2" and best["explains"] == 4
        kept = agent.keep_reading(str(song_file), "a#1/lead", best["index"])
        assert kept["dropped_note_edits"] == 4
        assert (
            agent.describe(str(song_file))["sections"]["a"]["tracks"]["lead"]["melody"] == "m; m +2"
        )
