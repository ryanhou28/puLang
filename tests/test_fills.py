"""
Drum fills: the drummer stops keeping time at the end of a phrase and plays a figure.

The promise under test: in a fill's beats the drum tracks rest except those kept,
the fill plays exactly its cells on the tracks it names, and nothing outside the
fill moves.
"""

from __future__ import annotations

import pytest

from pypulang import Role, grid, piece
from pypulang.compiler import compile_piece, parse_ir, print_ir
from pypulang.fills import FILLS, fill_cells
from pypulang.lift import daw_notes

BAR = 4 * 960


def song(fill=None, every=None, beats=2, keep=("pedal",), pitches=None, form=("a", "a")):
    with piece(tempo=120, key="C major", title="fills") as p:
        a = p.section("a", bars=4)
        a.chart("C | F | G | C")
        a.track("ride", role=Role.RHYTHM).pattern(grid(cell="x...x.x.x...x.x.", pitch=51))
        a.track("pedal", role=Role.RHYTHM).pattern(grid(cell="....x.......x...", pitch=44))
        a.track("snare", role=Role.RHYTHM).pattern(grid(cell="....x.......x...", pitch=38))
        a.track("kick", role=Role.RHYTHM).pattern(grid(cell="x.......x.......", pitch=36))
        if fill is not None:
            a.fill(fill, beats=beats, every=every, keep=keep, pitches=pitches)
        p.form(list(form))
    return p


def notes(p, tag="a#1"):
    found = daw_notes(compile_piece(p.to_ir()).daw)
    return {loc: n for loc, n in found.items() if loc.startswith(tag + "/")}


def track(found, name):
    return sorted(n[1] for loc, n in found.items() if loc.split("/")[1] == name)


class TestVocabulary:
    @pytest.mark.parametrize("name", list(FILLS))
    @pytest.mark.parametrize("steps", [2, 4, 8, 16])
    def test_every_named_fill_sizes_itself(self, name, steps):
        cells = fill_cells(name, steps)
        assert cells and all(len(cell) == steps for cell in cells.values())

    def test_an_unknown_fill_is_named(self):
        with pytest.raises(ValueError, match="'drum solo'"):
            fill_cells("drum solo", 8)


class TestAtTheEnd:
    def test_time_keepers_rest_for_the_fill_and_the_kept_one_plays_on(self):
        plain, filled = notes(song()), notes(song({"snare": "xxxxxxxX"}))
        window = 3 * BAR + 2 * 960
        assert [t for t in track(filled, "ride") if t >= window] == []
        assert track(filled, "pedal") == track(plain, "pedal")
        assert [t for t in track(filled, "snare") if t >= window] == [
            window + 240 * i for i in range(8)
        ]
        # Nothing before the fill moved
        for name in ("ride", "snare", "kick"):
            assert [t for t in track(filled, name) if t < window] == [
                t for t in track(plain, name) if t < window
            ]

    def test_accents_and_ghosts_carry_into_velocity(self):
        filled = notes(song({"snare": "o..X"}, beats=1))
        velocities = [
            n[3] for loc, n in sorted(filled.items(), key=lambda kv: kv[1][1]) if "/snare/" in loc
        ][-2:]
        assert velocities[0] < 96 < velocities[1]

    def test_a_short_cell_is_lined_up_with_the_downbeat(self):
        filled = notes(song({"snare": "xx"}, beats=2))
        assert track(filled, "snare")[-2:] == [4 * BAR - 480, 4 * BAR - 240]

    def test_a_tom_run_on_toms_that_only_play_in_fills(self):
        filled = notes(song("tom run", pitches={"tom_high": 50, "tom_low": 45}))
        assert len(track(filled, "tom_high")) == 2 and len(track(filled, "tom_low")) == 4

    def test_a_fill_track_with_no_note_is_refused_with_its_name(self):
        with pytest.raises(ValueError, match="'tom_high'"):
            notes(song("tom run"))

    def test_every_occurrence_fills(self):
        p = song({"snare": "xxxxxxxX"})
        assert len(track(notes(p, "a#2"), "snare")) == len(track(notes(p, "a#1"), "snare"))


class TestEveryFewBars:
    def test_a_fill_at_the_end_of_every_two_bars(self):
        filled = notes(song("setup", every=2, beats=1))
        ride = track(filled, "ride")
        for end in (2 * BAR, 4 * BAR):
            assert not [t for t in ride if end - 960 <= t < end]
        assert [t for t in ride if BAR - 960 <= t < BAR]  # bar 1 keeps time


class TestIr:
    def test_a_fill_prints_and_reads_back(self):
        module = compile_piece(song({"snare": "xxxxxxxX"}).to_ir(), until="intent").stages["intent"]
        text = print_ir(module)
        assert "intent.fill" in text
        again = compile_piece(parse_ir(text))
        assert daw_notes(again.daw) == daw_notes(
            compile_piece(song({"snare": "xxxxxxxX"}).to_ir()).daw
        )

    def test_a_transformed_section_keeps_its_fill(self):
        p = song({"snare": "xxxxxxxX"})
        a = p._sections[0]
        a.transform("b")
        p.form(["a", "b"])
        # Clip times count from each clip's start
        assert track(notes(p, "b#1"), "snare")[-8:] == track(notes(p, "a#1"), "snare")[-8:]
