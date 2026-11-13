"""
The compose view: notes on a staff, a melody as chips and the gestures on them,
and an edit previewed against the song before it is kept.
"""

from __future__ import annotations

import json
import threading
from fractions import Fraction as F

import pytest

from pypulang.compiler.edits import Edit
from pypulang.compose import Snapshot, chips, compare, motif_text, phrase_op
from pypulang.ir.intent import Key, TimeSignature
from pypulang.notation import Staff, StaffNote, _pieces, engrave, fifths, spell, to_mei
from pypulang.serve import Companion
from pypulang.songfile import load_song

SONG = """
from pypulang import *

with piece(tempo=100, key="D minor", title="compose") as song:
    song.motif("m", "r/8 5/8 6 5 3/4. 1/8 | 2/2 r/2")
    song.motif("n", "1/4 #7, 1/2")
    a = song.section("a", bars=4)
    a.chart("Dm9 | Bbmaj7 | Gm7 | A7")
    a.track("lead", role=Role.MELODY).melody("m; m -1", low=60, high=76)
    a.track("bass", role=Role.BASS).pattern(root_quarters)
    b = a.transform("b")
    song.form([a, b])
"""


@pytest.fixture
def song_path(tmp_path):
    path = tmp_path / "compose_song.py"
    path.write_text(SONG)
    return path


# -- notation ---------------------------------------------------------------------------


def test_a_degree_keeps_its_letter():
    d_minor = Key("D", "minor")
    assert spell(61, d_minor) == ("C", 1, 4)  # the raised seventh is C#, not Db
    assert spell(70, d_minor) == ("B", -1, 4)
    assert fifths(d_minor) == -1
    assert fifths(Key("Eb", "minor")) == -6
    assert fifths(Key("D", "dorian")) == 0
    assert fifths(Key("A", "major")) == 3


def test_rests_are_split_on_beats_and_never_dotted():
    values = [v for v, _, _ in _pieces(F(1), F(3), F(4), rest=True)]
    assert values == [1, 2]  # a quarter rest, then a half rest on the half bar
    values = [v for v, _, _ in _pieces(F(0), F(3, 2), F(4))]
    assert values == [F(3, 2)]  # a note may be dotted


def test_the_staff_ties_across_the_barline_and_shows_accidentals():
    notes = [StaffNote(69, F(0), F(1, 2), "a"), StaffNote(61, F(3), F(2), "b")]
    mei, rounded = to_mei(Staff(notes, 2, Key("D", "minor"), TimeSignature(4, 4)))
    assert rounded == 0
    assert 'key.sig="1f"' in mei
    assert 'pname="c" oct="4" dur="4" accid="s" tie="i"' in mei
    assert 'tie="t"' in mei and 'accid.ges="s" tie="t"' in mei  # not shown again
    assert mei.count("<measure") == 2


def test_eighths_in_one_beat_share_a_beam():
    notes = [StaffNote(62 + i, F(i, 2), F(1, 2), str(i)) for i in range(4)]
    mei, _ = to_mei(Staff(notes, 1, Key("C", "major"), TimeSignature(4, 4)))
    assert mei.count("<beam>") == 2


def test_engraving_works_from_any_thread():
    pytest.importorskip("verovio")
    staff = Staff([StaffNote(60, F(0), F(4), "c")], 1, Key("C", "major"), TimeSignature(4, 4))
    found: list[str] = []
    thread = threading.Thread(target=lambda: found.append(engrave(staff).svg))
    thread.start()
    thread.join()
    assert found and 'id="nc"' in found[0]


# -- chips --------------------------------------------------------------------------------


def test_a_phrase_is_chips_with_their_spans():
    shown = chips("m; rest 2; m -1", {"m": "r/8 5/8 6 5 3/4. 1/8 | 2/2 r/2"})
    assert [(c["text"], c["start"], c["length"]) for c in shown] == [
        ("m", 0, 8),
        ("rest 2", 8, 2),
        ("m -1", 10, 8),
    ]
    assert shown[1]["motif"] is None


def test_chip_gestures_rewrite_one_placement():
    phrase = "m; m -2; m vary 2; n"
    assert phrase_op(phrase, 1, "up") == "m; m -1; m vary 2; n"
    assert phrase_op(phrase_op(phrase, 1, "up"), 1, "up") == "m; m; m vary 2; n"
    assert phrase_op(phrase, 0, "octave_up") == "m ^; m -2; m vary 2; n"
    assert phrase_op(phrase, 0, "inv") == "m inv; m -2; m vary 2; n"
    assert phrase_op("m inv", 0, "inv") == "m"
    assert phrase_op(phrase, 2, "vary") == "m; m -2; m vary 3; n"
    assert phrase_op(phrase, 1, "motif", "n") == "m; n -2; m vary 2; n"
    assert phrase_op(phrase, 0, "first", "3") == "m first 3; m -2; m vary 2; n"
    assert phrase_op(phrase, 3, "insert", "rest 2") == "m; m -2; m vary 2; n; rest 2"
    assert phrase_op(phrase, 0, "right") == "m -2; m; m vary 2; n"
    assert phrase_op(phrase, 1, "delete") == "m; m vary 2; n"
    with pytest.raises(ValueError):
        phrase_op("rest 2", 0, "up")


def test_motif_notes_from_the_grid_are_written_as_motif_text():
    notes = [
        {"step": 4, "acc": 0, "s": 0, "d": 1},
        {"step": 6, "acc": 1, "s": 1, "d": 0.5},
        {"step": 0, "acc": 0, "s": 2, "d": 2, "accent": 1},
    ]
    assert motif_text(notes, 4) == "5/4 #7/8 r 1/2>"
    with pytest.raises(ValueError):
        motif_text([{"step": 0, "s": 0, "d": 2}, {"step": 1, "s": 1, "d": 1}], 4)


# -- previews ---------------------------------------------------------------------------


def test_a_motif_edit_reaches_every_section_that_states_it(song_path):
    song = load_song(song_path)
    before = Snapshot(song.compile(until="score"))
    after = Snapshot(
        song.compile(until="score", edits=[Edit("intent", "motif/n", "notes", "1/4 7, 1/2")])
    )
    assert compare(before, after).added == 0  # n is defined but not used
    after = Snapshot(
        song.compile(
            until="score",
            edits=[Edit("intent", "motif/m", "notes", "r/8 5/8 6 5 4/4. 1/8 | 2/2 r/2")],
        )
    )
    change = compare(before, after)
    assert change.tags() == ["a#1", "b#1"]
    assert {track for _, track in change.parts} == {"lead"}
    assert change.added == change.removed == 4  # one note in each of the four statements


def test_the_song_view_lists_the_form_and_each_motif_with_its_uses(song_path):
    snap = Snapshot(load_song(song_path).compile(until="score"))
    song = snap.song()
    assert [o["tag"] for o in song["form"]] == ["a#1", "b#1"]
    assert song["sections"]["b"]["derived"] == "a"
    uses = {m["name"]: [(u["section"], u["text"]) for u in m["uses"]] for m in song["motifs"]}
    assert uses["m"] == [("a", "m"), ("a", "m -1"), ("b", "m"), ("b", "m -1")]
    section = snap.section("a#1")
    assert [c["symbol"] for c in section["chords"]] == ["Dm9", "Bbmaj7", "Gm7", "A7"]
    assert section["chords"][0]["tones"] == [0, 2, 4, 5, 9]
    lead = next(p for p in section["parts"] if p["track"] == "lead")
    assert lead["melody"]["chips"][1]["text"] == "m -1" and lead["notes"]


def test_the_companion_previews_keeps_and_flips(song_path):
    companion = Companion(song_path, None)
    view = companion.compose_view({"tag": "a#1"})
    assert view["track"] == "lead" and view["pending"] == [] and "svg" in view["staff"]
    view = companion.compose_view(
        {"tag": "a#1", "change": {"kind": "phrase", "target": "a/lead", "index": 1, "op": "up"}}
    )
    assert view["pending"] == [
        {"target": "a/lead", "field": "melody", "value": "m; m", "was": "m; m -1"}
    ]
    assert view["change"]["tags"] == ["a#1", "b#1"]  # b is made from a, so it follows
    # A second gesture works on the pending value, not the saved one
    view = companion.compose_view(
        {
            "tag": "a#1",
            "pending": view["pending"],
            "change": {"kind": "phrase", "target": "a/lead", "index": 1, "op": "up"},
        }
    )
    assert view["pending"][0]["value"] == "m; m +1"
    # Keeping it writes the overrides; before and after swap them
    companion.compose_apply(view["pending"])
    overrides = song_path.parent / "compose_song.pulang" / "overrides.json"
    assert json.loads(overrides.read_text())["edits"][0]["value"] == "m; m +1"
    companion.compose_ab("before")
    assert not overrides.exists() or json.loads(overrides.read_text())["edits"] == []
    companion.compose_ab("after")
    assert json.loads(overrides.read_text())["edits"][0]["value"] == "m; m +1"


def test_a_change_that_cannot_compile_is_refused_and_the_rest_kept(song_path):
    companion = Companion(song_path, None)
    view = companion.compose_view(
        {
            "tag": "a#1",
            "change": {"kind": "set", "target": "a/lead", "field": "melody", "value": "zz"},
        }
    )
    assert view["error"] and view["pending"] == []
    view = companion.compose_view(
        {
            "tag": "a#1",
            "change": {
                "kind": "set",
                "target": "a/harmony@2+0",
                "field": "chord",
                "value": "Ebmaj7",
            },
        }
    )
    assert view["error"] is None and view["pending"][0]["value"] == "Ebmaj7"
    assert view["section"]["chords"][1]["symbol"] == "Ebmaj7"
