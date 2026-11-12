"""
What an agent writing a song through the tools ran into, each fixed and held.

The first agent to compose with puLang's tools reported what got in its way.
These pin the fixes: a pattern edit that crashed, a variation silently hidden by
hand edits, errors without a place, a range nobody checked, missing level control.
"""

from __future__ import annotations

import json
from fractions import Fraction

import pytest

from pypulang import agent
from pypulang.cli import main
from pypulang.compiler import compile_piece
from pypulang.compiler.check import review
from pypulang.compiler.dialects import daw
from pypulang.compiler.edits import Edit
from pypulang.harmony import chord_symbol, parse_chord_symbol
from pypulang.ir.intent import Key
from pypulang.songfile import load_song

SONG = """
from pypulang import *

with piece(tempo=80, key="F minor", title="report") as song:
    song.motif("m", "5/4 6 5 3")
    a = song.section("a", bars=2)
    a.chart("Fm9 | Bbm7 Eb7")
    a.track("lead", role=Role.MELODY).melody("m; m -1", low=60, high=76)
    a.track("bass", role=Role.BASS).pattern(riff(cell="x.......x.......", degrees="1 5", gate=0.9))
    a.track("keys", role=Role.HARMONY).pattern(comp).voicing("rootless", 53, 74)
    song.rack("keys", device("rev", "reverb"), volume=0.6)
    b = song.section("b", bars=2, tempo=70)
    b.chart("Dbmaj7 | C7")
    b.track("lead", role=Role.MELODY).melody("m ^", low=60, high=76)
    b.fermata(2, hold=2)
    song.form([a, b])
"""


@pytest.fixture
def song(tmp_path):
    path = tmp_path / "report.py"
    path.write_text(SONG)
    return str(path)


class TestEdits:
    def test_a_pattern_with_fractional_parameters_can_be_edited_and_saved(self, song):
        found = agent.edit(
            song, "a/bass", "pattern", 'riff {"cell": "x...x...x...x...", "degrees": "1"}'
        )
        assert found["from"]["params"]["gate"] == "9/10"  # kept as an exact fraction
        with open(song.replace(".py", ".pulang/overrides.json")) as f:
            saved = json.load(f)
        assert saved["edits"][0]["base"]["params"]["gate"] == "9/10"
        # and the saved edit is not stale against the source it was made on
        assert not agent.describe(song)["warnings"]

    def test_a_track_volume_is_an_edit(self, song):
        found = agent.edit(song, "rack/keys", "volume", 0.5)
        assert found["from"] == 0.6 and found["to"] == 0.5
        result = compile_piece(
            load_song(song).source,
            edits=[Edit("intent", "rack/keys", "volume", 0.5, 0.6)],
        )
        project = next(o for o in result.daw.body.block.ops if isinstance(o, daw.ProjectOp))
        assert next(t for t in project.tracks() if t.track.data == "keys").volume.value.data == 0.5


class TestVariations:
    def test_proposing_says_when_hand_edits_hide_part_of_the_bundle(self, song):
        agent.edit(song, "a/lead", "melody", "m; m -2")
        found = agent.propose(
            song,
            "lead",
            "up",
            [
                {"target": "a/lead", "field": "melody", "value": "m; m +1"},
                {"target": "motif/m", "field": "notes", "value": "5/4 6 1' 5"},
            ],
        )
        assert any("intent:a/lead:melody" in w and "override" in w for w in found["warnings"])
        listed = agent.variations(song)["lead"]["alternatives"][0]
        assert listed["overridden_by_hand_edits"] == ["intent:a/lead:melody"]


class TestPlaces:
    def test_a_tempo_kaidaw_cannot_play_is_an_error_naming_where(self, tmp_path):
        path = tmp_path / "slow.py"
        path.write_text(
            SONG.replace(
                "b.fermata(2, hold=2)", "b.ritardando(to=25, bars=1).fermata(2, beat=3, hold=3)"
            )
        )
        with pytest.raises(ValueError, match=r"b#1: the tempo reaches .* bpm at beat 7"):
            agent.describe(str(path))

    def test_a_voicing_that_does_not_fit_names_its_place_and_chord(self, tmp_path):
        path = tmp_path / "tight.py"
        path.write_text(SONG.replace('voicing("rootless", 53, 74)', 'voicing("rootless", 60, 64)'))
        with pytest.raises(
            ValueError, match=r"a#1/keys/c0: no rootless voicing of Fm9 fits MIDI 60-64"
        ):
            agent.describe(str(path))

    def test_a_dominant_seven_sharp_eleven_voices_rootless(self):
        from pypulang.compiler.passes.voice_lead import candidates_for, parse_spec

        key = Key("F", "minor")
        name, register = parse_spec("rootless(53,74)")
        assert candidates_for(name, parse_chord_symbol("A7#11", key), key, register)

    def test_check_names_section_and_bar(self, song):
        result = load_song(song).compile(until="score")
        found = review(result.stages["score"], result.stages["intent"])
        assert all("beat " not in f.location for f in found.findings)

    def test_a_melody_carried_far_past_its_range_is_reported(self, song):
        found = agent.review(song)
        assert found["findings"]["beyond its range"]["count"] > 0  # "m ^" lifts b's line an octave
        first = found["findings"]["beyond its range"]["first"][0]
        assert first["location"].startswith("b#1/lead/")


class TestTools:
    def test_the_agent_cli_lists_its_tools_and_their_arguments(self, capsys):
        assert main(["agent"]) == 0
        out = capsys.readouterr().out
        assert "propose:" in out and "site: string, required" in out

    def test_a_missing_argument_says_what_the_tool_takes(self, song, capsys):
        assert main(["agent", "edit", json.dumps({"song": song})]) == 1
        err = capsys.readouterr().err
        assert "missing a required argument: 'target'" in err and "field: string, required" in err

    def test_ir_of_one_section_at_the_score_stage(self, song):
        text = agent.ir(song, "score", "b")
        assert text and all("form/b#" in line for line in text.splitlines())

    def test_a_ramp_is_named_for_its_direction(self, tmp_path):
        path = tmp_path / "rit.py"
        path.write_text(SONG.replace("b.fermata(2, hold=2)", "b.ritardando(to=60, bars=1)"))
        assert (
            agent.describe(str(path))["sections"]["b"]["tempo_changes"][0]["kind"] == "ritardando"
        )


class TestSpelling:
    @pytest.mark.parametrize(
        ("written", "spelled"),
        [
            ("Dbmaj9", "Dbmaj9"),
            ("Fm(maj7)/E", "Fm(maj7)/E"),
            ("Ebmaj9#11", "Ebmaj9#11"),
            ("Fm6/9", "Fm6/9"),
        ],
    )
    def test_chords_are_spelled_as_a_chart_writes_them(self, written, spelled):
        key = Key("F", "minor")
        assert chord_symbol(parse_chord_symbol(written, key), key) == spelled

    def test_cut_notes_are_named(self, tmp_path):
        path = tmp_path / "long.py"
        # The lead laid back half a beat, so its last note in a runs into b
        path.write_text(
            SONG
            + "\nfrom pypulang.compiler.passes.perform import LayBack\n"
            + 'pipeline = {"event": [LayBack(ticks=480, tracks=("lead",))]}\n'
        )
        warnings = load_song(path).compile().warnings
        cut = next(w for w in warnings if "were cut" in w)
        assert "a#1/lead/" in cut


def test_fractions_are_kept_exactly():
    assert Edit("intent", "a/b", "pattern", {"params": {"gate": Fraction(9, 10)}}).to_json()[
        "value"
    ] == {"params": {"gate": "9/10"}}
