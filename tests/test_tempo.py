"""
Tempo as music: a section's own tempo, ritardando and accelerando, and fermatas.

The promise under test: a song whose tempo never moves lowers as it always has; a
section with no tempo of its own is back at the piece's; a ritardando takes as
long as its ramp says; a fermata holds its beat that many times as long and the
music picks up where it was; and the map reaches kaiDAW and MIDI whole.
"""

from __future__ import annotations

import math
from fractions import Fraction

import mido
import pytest

from pypulang import Role, block_chords, piece
from pypulang.backends.kaidaw import KaidawClient, SongState, push
from pypulang.backends.midi import event_to_midi
from pypulang.compiler import compile_piece, parse_ir, print_ir
from pypulang.compiler.edits import Edit
from pypulang.compiler.tempo import seconds_at, stream_points
from tests.fake_kaidaw import FakeKaidaw


def song(b_tempo=None, rit=None, fermata=None):
    with piece(tempo=120, key="C major", title="tempo") as p:
        a = p.section("a", bars=2)
        a.chart("C | G7")
        a.track("keys", role=Role.HARMONY).pattern(block_chords)
        b = p.section("b", bars=4, tempo=b_tempo)
        b.chart("C | F | G | C")
        b.track("keys", role=Role.HARMONY).pattern(block_chords)
        if rit is not None:
            b.ritardando(to=rit, bars=2)
        if fermata is not None:
            b.fermata(*fermata)
        p.form([a, b, a])
    return p


def tempo_map(p, edits=()):
    return stream_points(compile_piece(p.to_ir(), until="event", edits=edits).stages["event"])


class TestMap:
    def test_a_steady_song_has_one_tempo_and_no_tempo_ops(self):
        result = compile_piece(song().to_ir(), until="score")
        assert "score.tempo" not in print_ir(result.stages["score"])
        assert tempo_map(song()) == [(0, 120.0)]

    def test_a_section_tempo_holds_for_that_section_and_then_it_is_back_a_tempo(self):
        assert tempo_map(song(b_tempo=90)) == [(0, 120.0), (8, 90.0), (24, 120.0)]

    def test_a_ritardando_steps_down_every_half_beat_and_lands_on_its_tempo(self):
        points = tempo_map(song(rit=60))
        ramp = [(at, bpm) for at, bpm in points if 16 <= at < 24]
        assert [at for at, _ in ramp] == [16 + Fraction(k, 2) for k in range(16)]
        assert all(x[1] > y[1] for x, y in zip(ramp, ramp[1:], strict=False))
        assert ramp[0][1] == pytest.approx(120 - 60 / 32) and ramp[-1][1] == pytest.approx(
            60 + 60 / 32
        )
        # Stepped at the middle of each half beat, it lasts as long as the true ramp:
        # the integral of 60/bpm over a linear fall from 120 to 60 across 8 beats
        exact = 8 * 60 / (120 - 60) * math.log(120 / 60)
        assert seconds_at(24, points) - seconds_at(16, points) == pytest.approx(exact, rel=1e-3)

    def test_a_fermata_holds_its_beat_that_many_times_as_long(self):
        plain, held = tempo_map(song()), tempo_map(song(fermata=(4, 0, 3, 1)))
        assert seconds_at(32, held) - seconds_at(32, plain) == pytest.approx(2 * 0.5)
        assert seconds_at(20, held) == seconds_at(20, plain)

    def test_a_fermata_inside_a_ritardando_picks_the_ramp_up_where_it_was(self):
        ramped = dict(tempo_map(song(rit=60)))
        both = dict(tempo_map(song(rit=60, fermata=(4, 0, 3, 1))))
        assert both[Fraction(20)] == pytest.approx(ramped[Fraction(20)] / 3)
        assert both[Fraction(21)] == pytest.approx(ramped[Fraction(21)])

    def test_changes_that_do_not_fit_are_refused(self):
        with pytest.raises(ValueError, match="does not fit"):
            _too_long()
        with pytest.raises(ValueError, match="outside 20 to 300"):
            song(b_tempo=1000)


def _too_long():
    with piece(tempo=120) as p:
        p.section("a", bars=2).ritardando(to=80, bars=3)


class TestDownstream:
    def test_midi_carries_every_tempo(self):
        midi = event_to_midi(compile_piece(song(rit=60).to_ir(), until="event").stages["event"])
        tempos = [m for track in midi.tracks for m in track if m.type == "set_tempo"]
        assert len(tempos) == len(tempo_map(song(rit=60)))
        assert mido.tempo2bpm(tempos[0].tempo) == pytest.approx(120)

    def test_kaidaw_gets_the_whole_map(self, tmp_path):
        client = KaidawClient(transport=FakeKaidaw())
        push(
            compile_piece(song(b_tempo=90).to_ir()).daw,
            client,
            SongState(tmp_path / "s.pulang"),
            fresh=True,
        )
        bpms = [p["bpm"] for p in client.projection()["tempoMap"]]
        assert bpms == [120.0, 90.0, 120.0]

    def test_the_ir_prints_and_reads_back(self):
        module = compile_piece(song(b_tempo=90, rit=60).to_ir(), until="intent").stages["intent"]
        text = print_ir(module)
        assert "tempo 9.000000e+01" in text and "intent.tempo" in text
        assert stream_points(
            compile_piece(parse_ir(text), until="event").stages["event"]
        ) == tempo_map(song(b_tempo=90, rit=60))


class TestEdits:
    def test_a_section_tempo_is_an_intent_edit(self):
        edit = Edit("intent", "b", "tempo", 100.0, None)
        result = compile_piece(song().to_ir(), until="event", edits=[edit])
        assert result.edits.applied == [edit.key] and not result.edits.stale
        assert stream_points(result.stages["event"]) == [(0, 120.0), (8, 100.0), (24, 120.0)]

    def test_none_takes_a_section_back_to_the_piece_tempo(self):
        assert tempo_map(song(b_tempo=90), [Edit("intent", "b", "tempo", None, 90.0)]) == [
            (0, 120.0)
        ]
