"""
Round trips between a song and a DAW project.

The promise under test: you can edit in the DAW and keep composing in source.
Recompiling never discards a hand edit, and undoing a recompile is one step.
"""

from __future__ import annotations

import pytest

from pypulang import IV, I, Role, V, block_chords, ii, piece, root_eighths, root_quarters, vi
from pypulang.backends.kaidaw import KaidawError, SongState, pull, push, status
from pypulang.compiler import compile_piece
from pypulang.pitches import A5, B5, G5


def song(chords=(I, vi, IV, V), bass=root_quarters, keys=block_chords, volume=None):
    with piece(tempo=120, key="G major", title="sync") as p:
        verse = p.section("verse", bars=4)
        verse.harmony(*chords)
        verse.track("bass", role=Role.BASS).pattern(bass).octave(-2)
        verse.track("keys", role=Role.HARMONY).pattern(keys, rate=1 / 2)
        verse.track("lead", role=Role.MELODY).notes(
            [(B5, 1 / 2), (A5, 1 / 2), (G5, 1 / 2), (A5, 1 / 2)]
        )
        chorus = p.section("chorus", bars=4)
        chorus.harmony(IV, V, I, I)
        chorus.track("bass", role=Role.BASS).pattern(root_eighths).octave(-2)
        chorus.track("keys", role=Role.HARMONY).pattern(keys, rate=1 / 4)
        p.form([verse, chorus, verse])
        if volume is not None:
            p.rack("keys", volume=volume)
    return compile_piece(p.to_ir()).daw


@pytest.fixture
def state(tmp_path) -> SongState:
    return SongState(tmp_path / "song.pulang")


def daw_notes(client, clip_id):
    clip = next(c for c in client.projection()["clips"] if c["id"] == clip_id)
    return sorted((n["pitch"], n["start"], n["duration"], n["velocity"]) for n in clip["notes"])


def locate(state, loc):
    lock = state.load_lock()
    entry = lock.notes[loc]
    return lock.clips[entry["clip"]]["id"], entry["id"], entry["note"]


def hand_edit(client, operations):
    client.apply(operations, client.revision(), "by hand")


def wire(note, note_id=None):
    data = {"pitch": note[0], "start": note[1], "duration": note[2], "velocity": note[3]}
    if note_id:
        data["id"] = note_id
    return data


class TestPush:
    def test_first_push_builds_the_song(self, client, state):
        report = push(song(), client, state)
        projection = client.projection()
        names = {t["name"] for t in projection["tracks"]}
        assert {"bass", "keys", "lead"} <= names
        # verse, chorus, verse on bass and keys; lead only in the verses
        assert len(projection["clips"]) == 8
        total = sum(len(c["notes"]) for c in projection["clips"])
        assert total == report.notes_added > 0

    def test_second_push_of_the_same_song_changes_nothing(self, client, state):
        push(song(), client, state)
        revision = client.revision()
        report = push(song(), client, state)
        assert report.operations == 0
        assert client.revision() == revision

    def test_repeated_section_is_two_clips_with_stable_names(self, client, state):
        push(song(), client, state)
        lock = state.load_lock()
        assert "verse#1/bass" in lock.clips and "verse#2/bass" in lock.clips
        assert lock.clips["verse#1/bass"]["id"] != lock.clips["verse#2/bass"]["id"]

    def test_changing_one_chord_touches_only_its_notes(self, client, state):
        push(song(), client, state)
        report = push(song(chords=(I, vi, ii, V)), client, state)
        assert report.notes_added == 0 and report.notes_deleted == 0
        # IV became ii in both verses: one bar of bass and of keys, twice over
        assert report.notes_updated == 2 * (4 + 2 * 3)
        assert report.tracks_created == 0 and report.clips_created == 0

    def test_a_push_is_one_undo_step(self, client, state):
        push(song(), client, state)
        before = client.projection()["clips"]
        push(song(chords=(I, vi, ii, V)), client, state)
        client.undo()
        after = client.projection()["clips"]
        strip = lambda clips: sorted(  # noqa: E731
            (c["id"], sorted((n["id"], n["pitch"]) for n in c["notes"])) for c in clips
        )
        assert strip(after) == strip(before)


class TestHandEdits:
    def test_a_moved_note_survives_a_recompile(self, client, state):
        push(song(), client, state)
        clip, note_id, note = locate(state, "verse#1/lead/1+2/v0")
        edited = [note[0] + 2, note[1], note[2], 110]
        hand_edit(
            client, [{"type": "UpsertNotes", "clipId": clip, "notes": [wire(edited, note_id)]}]
        )
        push(song(chords=(I, vi, ii, V)), client, state)
        assert tuple(edited) in daw_notes(client, clip)

    def test_a_deleted_note_stays_deleted_when_the_harmony_changes_under_it(self, client, state):
        push(song(), client, state)
        # Bar 3 of the verse is the chord that is about to change
        clip, note_id, note = locate(state, "verse#1/bass/3+1/v0")
        hand_edit(client, [{"type": "DeleteNotes", "clipId": clip, "noteIds": [note_id]}])
        report = push(song(chords=(I, vi, ii, V)), client, state)
        assert not [n for n in daw_notes(client, clip) if n[1] == note[1]]
        assert any("3+1" in s for s in report.stale)

    def test_a_note_drawn_by_hand_survives(self, client, state):
        push(song(), client, state)
        clip, _, _ = locate(state, "verse#1/lead/1+0/v0")
        drawn = [100, 960, 240, 90]
        hand_edit(client, [{"type": "UpsertNotes", "clipId": clip, "notes": [wire(drawn)]}])
        push(song(chords=(I, vi, ii, V)), client, state)
        push(song(chords=(I, vi, IV, V)), client, state)
        assert daw_notes(client, clip).count(tuple(drawn)) == 1

    def test_moving_a_note_back_clears_the_override(self, client, state):
        push(song(), client, state)
        clip, note_id, note = locate(state, "verse#1/lead/1+2/v0")
        hand_edit(
            client,
            [
                {
                    "type": "UpsertNotes",
                    "clipId": clip,
                    "notes": [wire([note[0] + 1, *note[1:]], note_id)],
                }
            ],
        )
        pull(client, state)
        assert state.load_overrides().count == 1
        push(song(), client, state)
        hand_edit(client, [{"type": "UpsertNotes", "clipId": clip, "notes": [wire(note, note_id)]}])
        pull(client, state)
        assert state.load_overrides().count == 0

    def test_a_hand_edit_is_kept_when_the_source_stops_making_the_note(self, client, state):
        push(song(), client, state)
        clip, note_id, note = locate(state, "verse#1/bass/1+1/v0")
        edited = [note[0] + 5, *note[1:]]
        hand_edit(
            client, [{"type": "UpsertNotes", "clipId": clip, "notes": [wire(edited, note_id)]}]
        )
        # At half-note rate there is no bass note on beat 2 any more
        report = push(song(bass=block_chords(rate=2)), client, state)
        assert tuple(edited) in daw_notes(client, clip)
        assert any("1+1" in s for s in report.orphaned)

    def test_stale_edit_is_reported(self, client, state):
        push(song(), client, state)
        clip, note_id, note = locate(state, "verse#1/bass/3+0/v0")
        edited = [note[0], note[1], note[2], 60]
        hand_edit(
            client, [{"type": "UpsertNotes", "clipId": clip, "notes": [wire(edited, note_id)]}]
        )
        report = push(song(chords=(I, vi, ii, V)), client, state)
        assert len(report.stale) == 1 and "3+0" in report.stale[0]
        assert tuple(edited) in daw_notes(client, clip)

    def test_a_moved_clip_stays_moved(self, client, state):
        push(song(), client, state)
        lock = state.load_lock()
        clip = lock.clips["chorus#1/bass"]["id"]
        target = lock.clips["chorus#1/bass"]["start"] + 960
        hand_edit(client, [{"type": "MoveClip", "clipId": clip, "start": target}])
        push(song(chords=(I, vi, ii, V)), client, state)
        live = next(c for c in client.projection()["clips"] if c["id"] == clip)
        assert live["start"] == target

    def test_a_deleted_clip_stays_deleted(self, client, state):
        push(song(), client, state)
        clip = state.load_lock().clips["verse#2/keys"]["id"]
        hand_edit(client, [{"type": "DeleteClip", "clipId": clip}])
        push(song(chords=(I, vi, ii, V)), client, state)
        assert "verse#2/keys" not in {c["name"] for c in client.projection()["clips"]}

    def test_a_clip_made_by_hand_is_left_alone(self, client, state):
        push(song(), client, state)
        lock = state.load_lock()
        track = lock.tracks["lead"]["id"]
        hand_edit(
            client,
            [
                {
                    "type": "CreateClip",
                    "alias": "$mine",
                    "trackId": track,
                    "name": "mine",
                    "start": 96000,
                    "length": 3840,
                    "notes": [wire([72, 0, 960, 100])],
                }
            ],
        )
        push(song(chords=(I, vi, ii, V)), client, state)
        assert "mine" in {c["name"] for c in client.projection()["clips"]}


class TestOwnership:
    def test_a_fader_moved_by_hand_stays_until_the_source_changes(self, client, state):
        push(song(volume=0.6), client, state)
        track = state.load_lock().tracks["keys"]["id"]
        hand_edit(client, [{"type": "SetTrackState", "trackId": track, "volume": 0.3}])

        def live():
            return next(t for t in client.projection()["tracks"] if t["id"] == track)["volume"]

        push(song(volume=0.6, chords=(I, vi, ii, V)), client, state)
        assert live() == pytest.approx(0.3, abs=1e-3)
        push(song(volume=0.5), client, state)
        assert live() == pytest.approx(0.5, abs=1e-3)

    def test_a_plugin_added_by_hand_survives(self, client, state):
        push(song(), client, state)
        track = state.load_lock().tracks["keys"]["id"]
        hand_edit(
            client,
            [{"type": "AddPlugin", "alias": "$r", "trackId": track, "identifier": "reverb"}],
        )
        before = next(t for t in client.projection()["tracks"] if t["id"] == track)["pluginIds"]
        push(song(chords=(I, vi, ii, V)), client, state)
        after = next(t for t in client.projection()["tracks"] if t["id"] == track)["pluginIds"]
        assert after == before


class TestSaveAndReopen:
    def test_a_song_reconnects_to_a_reopened_project(self, client, state, tmp_path, request):
        push(song(), client, state)
        if "real" in request.node.name:
            path = r"C:\kaidaw-win\tmp\pulang-test.kaidaw"
        else:
            path = "fake-project"
        client.save(path)
        client.open(path)
        report = push(song(), client, state)
        assert report.operations == 0


class TestRefusals:
    def test_a_lock_for_another_project_is_refused(self, client, state):
        push(song(), client, state)
        projection = client.projection()
        client.apply(
            [{"type": "DeleteTrack", "trackId": t["id"]} for t in projection["tracks"]],
            projection["revision"],
            "someone else's project",
        )
        with pytest.raises(KaidawError, match="fresh"):
            push(song(), client, state)
        assert push(song(), client, state, fresh=True).tracks_created == 3

    def test_status_reports_without_changing_anything(self, client, state):
        push(song(), client, state)
        revision = client.revision()
        report = status(song(chords=(I, vi, ii, V)), client, state)
        assert report.notes_updated > 0
        assert client.revision() == revision
