"""
Variations, and puLang as tools an agent calls.

The promises under test: an alternative is a bundle of edits that only applies
when picked, the source is always one of the alternatives, a hand edit still has
the last word, and every change an agent asks for is checked by compiling before
it is kept, with what it does to the notes reported back.
"""

from __future__ import annotations

import io
import json

import pytest

from pypulang import agent
from pypulang.backends.kaidaw import KaidawClient, SongState, push
from pypulang.compiler.edits import Edit, current_value
from pypulang.harmony import chart_changes, chart_text
from pypulang.ir.intent import Key
from pypulang.lift import daw_notes
from pypulang.mcp import serve as serve_mcp
from pypulang.serve import Companion
from pypulang.songfile import load_song
from tests.fake_kaidaw import FakeKaidaw

SONG = """
from pypulang import *

with piece(tempo=120, key="D minor", title="small") as song:
    song.motif("hook", "5/8 6 5 3/4. 1/8 | 2/2 r/2")
    a = song.section("a", bars=4)
    a.chart("Dm9 | Gm9 | Em7b5 | A7b9")
    a.track("lead", role=Role.MELODY).melody("hook; hook -1", low=57, high=76)
    a.track("keys", role=Role.HARMONY).pattern(comp).voicing("rootless", 52, 72)
    a.track("bass", role=Role.BASS).pattern(walking_bass())
    b = song.section("b", bars=2)
    b.chart("Bbmaj7 | A7")
    b.track("bass", role=Role.BASS).pattern(walking_bass())
    song.form([a, b, a])
"""

D = Key("D", "minor")
HOOK_UP = [{"target": "motif/hook", "field": "notes", "value": "1'/8 7 6 5/4. 3/8 | #7,/2 r/2"}]


@pytest.fixture
def song(tmp_path):
    path = tmp_path / "small.py"
    path.write_text(SONG)
    return str(path)


def lead(path: str, tag: str = "a#1") -> list[int]:
    notes = daw_notes(load_song(path).compile().daw)
    return [
        n[0]
        for loc, n in sorted(notes.items(), key=lambda kv: kv[1][1])
        if loc.startswith(f"{tag}/lead/")
    ]


class TestCharts:
    def test_a_chart_reads_back_as_it_was_written(self):
        chart = "Dm9 | Gm9 | Em7b5 A7b9 | Dm9"
        assert chart_changes(chart_text(chart_changes(chart, D, 4), D), D, 4) == chart_changes(
            chart, D, 4
        )

    def test_a_short_chart_loops_and_a_long_one_stops(self):
        assert len(chart_changes("Dm9 | A7", D, 6)) == 6
        assert len(chart_changes("Dm9 | A7 | Gm7 | C7", D, 2)) == 2

    def test_a_held_chord_is_written_as_a_repeat_sign(self):
        from fractions import Fraction

        changes = chart_changes("Dm9", D, 1)
        assert chart_text([(changes[0][0], Fraction(2))], D) == "Dm9 | %"

    def test_a_chart_edit_replaces_the_progression(self, song):
        edit = Edit("intent", "a/harmony", "chart", "Dm9 | A7b9", "Dm9 | Gm9 | Em7b5 | A7b9")
        result = load_song(song).compile(edits=[edit])
        assert result.edits.applied == [edit.key] and not result.edits.stale
        _, now = current_value(result.stages["intent"], Edit("intent", "a/harmony", "chart", None))
        assert now == "Dm9 | A7b9 | Dm9 | A7b9"


class TestVariations:
    def test_a_proposal_is_kept_but_not_played_until_picked(self, song):
        before = lead(song)
        found = agent.propose(song, "hook", "hook-high", HOOK_UP, "from the octave down")
        assert found["effect"]["total"] > 0 and "a#1/lead" in found["effect"]["places"]
        assert lead(song) == before
        agent.pick(song, "hook", "hook-high")
        assert lead(song) != before
        assert lead(song, "a#2") == lead(song)  # a motif edit reaches every use
        agent.pick(song, "hook", "source")
        assert lead(song) == before

    def test_a_hand_edit_has_the_last_word(self, song):
        agent.propose(song, "hook", "hook-high", HOOK_UP)
        agent.pick(song, "hook", "hook-high")
        picked = lead(song)
        agent.edit(song, "a/lead", "octave", 1)
        assert lead(song) == [p + 12 for p in picked]

    def test_alternatives_at_a_site_replace_each_other(self, song):
        agent.propose(song, "hook", "hook-high", HOOK_UP)
        agent.propose(song, "hook", "hook-low", [{**HOOK_UP[0], "value": "5,/4 6, 7, 1/2 | 2/1"}])
        agent.pick(song, "hook", "hook-high")
        agent.pick(song, "hook", "hook-low")
        found = agent.variations(song)["hook"]
        assert found["picked"] == "hook-low"
        assert [a["name"] for a in found["alternatives"]] == ["hook-high", "hook-low"]

    def test_dropping_the_picked_variation_goes_back_to_the_source(self, song):
        before = lead(song)
        agent.propose(song, "hook", "hook-high", HOOK_UP)
        agent.pick(song, "hook", "hook-high")
        agent.drop_variation(song, "hook-high")
        assert lead(song) == before and agent.variations(song) == {}

    def test_a_variation_can_change_harmony_and_parts_together(self, song):
        found = agent.propose(
            song,
            "a harmony",
            "pedal",
            [
                {"target": "a/harmony", "field": "chart", "value": "Dm9 | Gm9/D | Em7b5/D | A7b9"},
                {"target": "a/keys", "field": "voicing", "value": "drop2(55,79)"},
            ],
        )
        assert {"a#1/keys", "a#1/bass"} <= set(found["effect"]["places"])


class TestRefusals:
    @pytest.mark.parametrize(
        ("edits", "reason"),
        [
            ([{"target": "motif/hook", "field": "notes", "value": "1/4 9"}], "cannot read"),
            ([{"target": "nowhere/lead", "field": "octave", "value": 1}], "no such place"),
            ([{"target": "a/lead", "field": "octave"}], "needs value"),
            ([{"target": "a/lead", "field": "octave", "value": 0}], "changes no notes"),
            ([{"target": "a/harmony", "field": "chart", "value": "H#q9"}], "cannot read"),
        ],
    )
    def test_a_bad_proposal_is_refused_and_not_kept(self, song, edits, reason):
        with pytest.raises(agent.ToolError, match=reason):
            agent.propose(song, "s", "v", edits)
        assert agent.variations(song) == {}

    def test_the_source_name_is_reserved(self, song):
        with pytest.raises(agent.ToolError):
            agent.propose(song, "hook", "source", HOOK_UP)

    def test_a_variation_is_picked_only_at_its_own_site(self, song):
        agent.propose(song, "hook", "hook-high", HOOK_UP)
        with pytest.raises(agent.ToolError, match="not 'verse'"):
            agent.pick(song, "verse", "hook-high")


class TestReading:
    def test_describe_gives_form_charts_parts_and_motifs(self, song):
        found = agent.describe(song)
        assert [f["section"] for f in found["form"]] == ["a#1", "b#1", "a#2"]
        assert found["form"][1]["bars"] == "5-6"
        assert found["sections"]["a"]["chart"] == "Dm9 | Gm9 | Em7b5 | A7b9"
        assert found["sections"]["a"]["tracks"]["lead"]["melody"] == "hook; hook -1"
        assert found["motifs"] == {"hook": "5/8 6 5 3/4. 1/8 | 2/2 r/2"}
        json.dumps(found)  # plain data all the way down

    def test_an_edit_reports_what_it_changed(self, song):
        found = agent.edit(song, "b/bass", "octave", -1)
        assert found["from"] == 0 and found["to"] == -1
        assert found["effect"]["places"] == ["b#1/bass"]
        assert agent.describe(song)["edits"][0]["target"] == "b/bass"

    def test_ir_of_one_section(self, song):
        text = agent.ir(song, "intent", "b")
        assert text.startswith('intent.section "b"') and "hook" not in text

    def test_review_measures_each_melody(self, song):
        found = agent.review(song)
        assert found["summary"].startswith("Strong-beat melody notes")
        assert found["melodies"]["lead"]["a#1"]["notes"] > 0


class TestMcp:
    def talk(self, *messages):
        out = io.StringIO()
        serve_mcp(io.StringIO("\n".join(json.dumps(m) for m in messages) + "\n"), out)
        return [json.loads(line) for line in out.getvalue().splitlines()]

    def test_it_lists_and_calls_tools(self, song):
        replies = self.talk(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "describe", "arguments": {"song": song}},
            },
        )
        assert [r["id"] for r in replies] == [1, 2, 3]  # the notification has no answer
        assert replies[0]["result"]["capabilities"] == {"tools": {}}
        names = {t["name"] for t in replies[1]["result"]["tools"]}
        assert {"describe", "edit", "propose", "pick", "audition"} <= names
        assert names == set(agent.TOOLS)
        body = replies[2]["result"]
        assert not body["isError"] and json.loads(body["content"][0]["text"])["title"] == "small"

    def test_a_failure_is_an_error_result_not_a_crash(self, song):
        (reply,) = self.talk(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "pick",
                    "arguments": {"song": song, "site": "x", "name": "nope"},
                },
            }
        )
        assert reply["result"]["isError"] and "nope" in reply["result"]["content"][0]["text"]


class TestCompanion:
    def test_the_page_lists_variations_and_picks_one(self, song):
        client = KaidawClient(transport=FakeKaidaw())
        push(load_song(song).compile().daw, client, SongState.beside(song), fresh=True)
        agent.propose(song, "hook", "hook-high", HOOK_UP, "from the octave down")
        companion = Companion(song, client)
        page = companion.page({})
        assert "Variations" in page and "hook-high" in page and "from the octave down" in page
        assert "pushed" in companion.pick("hook", "hook-high")
        assert agent.variations(song)["hook"]["picked"] == "hook-high"


class TestFocus:
    def test_alternatives_are_heard_where_they_change_most_not_where_they_are_teased(self):
        from pypulang.variations import Effect, focus

        teased = Effect(changed={"intro#1/lead": 4, "chorus#1/lead": 20, "chorus#2/lead": 21})
        order = ["intro#1", "verse#1", "chorus#1", "chorus#2"]
        assert focus([teased], order) == "chorus#1"
        assert focus([Effect()], order) is None
