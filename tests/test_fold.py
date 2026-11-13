"""
Folding edits into the song's source, and edits following `transform`.

An edit means what the same change to the source would, so a chorus made from
another follows its edits; folding then writes each edit where a person would
have, and checks by compiling that nothing else changed.
"""

from __future__ import annotations

import json

import pytest

from pypulang import agent
from pypulang.compiler.edits import Edit
from pypulang.fold import _chart_token_change, fold
from pypulang.songfile import load_song

SONG = """
from pypulang import *

LINE = "m; m -1"
CHART = "Fm9 | Bbm7 Eb7"
MOTIFS = {"m": "5/4 6 5 3", "n": "1/2 2 3"}


def band(section, velocity=70):
    section.track("keys", role=Role.HARMONY).pattern(comp).voicing("rootless", 53, 74).velocity(
        velocity
    )


with piece(tempo=80, key="F minor", title="fold") as song:
    for name, notes in MOTIFS.items():
        song.motif(name, notes)
    song.rack("keys", device("rev", "reverb"))
    song.rack("lead", device("rev2", "reverb"), volume=0.6)
    a = song.section("a", bars=2)
    a.chart(CHART)
    a.track("lead", role=Role.MELODY).melody(LINE, low=60, high=76)
    a.track("bass", role=Role.BASS).pattern(riff(cell="x.......x.......", degrees="1 5"))
    band(a)
    b = song.section("b", bars=2)
    b.chart(CHART)
    b.track("lead", role=Role.MELODY).melody(LINE, low=60, high=76).velocity(90)
    band(b)
    c = song.section("c", bars=2)
    c.chart("Dbmaj7 | C7")
    c.track("lead", role=Role.MELODY).melody("n; n +1", low=60, high=76)
    d = c.transform("d", transpose=1)
    song.form([a, b, c, d])
"""


@pytest.fixture
def song(tmp_path):
    path = tmp_path / "fold.py"
    path.write_text(SONG)
    return path


def notes(path, edits=None):
    result = load_song(path).compile(edits=edits)
    return str(result.stages["event"]) + str(result.daw)


def edited_then_folded(song, *edits):
    """Make the edits, fold, and check the song plays as it did with them."""
    for target, name, value in edits:
        agent.edit(str(song), target, name, value)
    before = notes(song)
    result = fold(song)
    assert notes(song) == before
    return result, song.read_text()


class TestFollowingTransforms:
    def test_a_section_made_from_another_follows_its_edits(self, song):
        result = load_song(song).compile(
            edits=[Edit("intent", "c/lead", "velocity", 70, 100)], until="intent"
        )
        assert result.edits.followed == {"intent:c/lead:velocity": ["d"]}

    def test_its_own_edit_wins(self, song):
        result = load_song(song).compile(
            edits=[
                Edit("intent", "c/lead", "velocity", 70, 100),
                Edit("intent", "d/lead", "velocity", 110, 100),
            ],
            until="intent",
        )
        assert result.edits.followed == {}

    def test_chords_follow_into_a_transposed_copy(self, song):
        from pypulang.compiler.edits import _intent_section, _piece, section_chart

        result = load_song(song).compile(
            edits=[Edit("intent", "c/harmony@2+0", "chord", "C7alt", "C7")], until="intent"
        )
        piece = _piece(result.stages["intent"])
        assert section_chart(_intent_section(piece, "d"), piece) == "Dmaj7 | C#7alt"


class TestFold:
    def test_a_literal_argument_is_rewritten(self, song):
        result, text = edited_then_folded(song, ("b/lead", "velocity", 80))
        assert "melody(LINE, low=60, high=76).velocity(80)" in text
        assert [e.key for e, _ in result.folded] == ["intent:b/lead:velocity"]

    def test_a_setting_never_written_is_added_to_the_chain(self, song):
        _, text = edited_then_folded(song, ("a/bass", "velocity", 64))
        assert 'a.track("bass", role=Role.BASS).velocity(64).pattern(' in text

    def test_a_setting_made_in_a_shared_helper_gets_its_own_line(self, song):
        _, text = edited_then_folded(song, ("a/keys", "voicing", "rootless(46,64)"))
        assert 'band(a)\n    a.track("keys").voicing("rootless", 46, 64)' in text
        assert 'voicing("rootless", 53, 74)' in text  # b keeps the helper's

    def test_a_constant_two_sections_share_is_left_alone(self, song):
        _, text = edited_then_folded(song, ("a/harmony@1+0", "chord", "Fm(maj7)"))
        assert 'CHART = "Fm9 | Bbm7 Eb7"' in text
        assert 'a.chart("Fm(maj7) | Bbm7 Eb7")' in text

    def test_one_chord_of_a_literal_chart_changes_alone(self, song):
        _, text = edited_then_folded(song, ("c/harmony@2+0", "chord", "C7alt"))
        assert 'c.chart("Dbmaj7 | C7alt")' in text

    def test_a_motif_in_a_dict_is_rewritten_in_the_dict(self, song):
        _, text = edited_then_folded(song, ("motif/m", "notes", "5/4 6 1' 5"))
        assert '"m": "5/4 6 1\' 5"' in text

    def test_a_rack_level_is_set_where_the_rack_is_declared(self, song):
        _, text = edited_then_folded(
            song, ("rack/keys", "volume", 0.5), ("rack/lead", "volume", 0.7)
        )
        assert 'song.rack("keys", device("rev", "reverb"), volume=0.5)' in text
        assert 'device("rev2", "reverb"), volume=0.7)' in text

    def test_an_edit_on_a_copy_goes_after_the_copy_is_made(self, song):
        _, text = edited_then_folded(song, ("d/lead", "velocity", 60))
        assert 'd = c.transform("d", transpose=1)\n    d.track("lead").velocity(60)' in text

    def test_an_edit_the_copy_follows_folds_into_the_original(self, song):
        _, text = edited_then_folded(song, ("c/lead", "melody", "n; n -1"))
        assert 'melody("n; n -1", low=60, high=76)' in text

    def test_folded_edits_leave_the_overrides(self, song):
        edited_then_folded(song, ("b/lead", "velocity", 80))
        saved = json.loads((song.parent / "fold.pulang" / "overrides.json").read_text())
        assert saved["edits"] == []

    def test_a_dry_run_writes_nothing(self, song):
        agent.edit(str(song), "b/lead", "velocity", 80)
        result = fold(song, write=False)
        assert song.read_text() == SONG
        assert "+    b.track" in result.diff and ".velocity(80)" in result.diff and result.folded
        saved = json.loads((song.parent / "fold.pulang" / "overrides.json").read_text())
        assert len(saved["edits"]) == 1

    def test_an_edit_below_the_source_is_kept(self, song):
        agent.edit(str(song), "b/lead", "velocity", 80)
        overrides = song.parent / "fold.pulang" / "overrides.json"
        data = json.loads(overrides.read_text())
        data["edits"].append(
            {"level": "score", "target": "a#1/keys/c0", "field": "pitches", "value": [53, 58, 63]}
        )
        overrides.write_text(json.dumps(data))
        result = fold(song)
        assert [e.key for e, _ in result.kept] == ["score:a#1/keys/c0:pitches"]


def test_a_chart_keeps_its_spelling_when_one_chord_changes():
    assert _chart_token_change("Fm9  | Bb9/D   %", "Fm9 | Bb13/D %") == "Fm9  | Bb13/D   %"


def test_the_agent_tool_reports_and_can_only_look(song):
    agent.edit(str(song), "b/lead", "velocity", 80)
    found = agent.fold(str(song), dry_run=True)
    assert found["folded"] == [{"edit": "intent:b/lead:velocity", "how": "b/lead velocity set"}]
    assert not found["written"] and ".velocity(80)" in found["diff"]
    assert song.read_text() == SONG
