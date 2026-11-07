"""The score review, and the generated solo line."""

from __future__ import annotations

from fractions import Fraction

from pypulang import Role, comp, hits, piece, solo_line, walking_bass
from pypulang.compiler import compile_piece
from pypulang.compiler.check import review
from pypulang.compiler.dialects import score
from pypulang.compiler.spelling import midi_of
from pypulang.ir.intent import Note


def score_of(p):
    return compile_piece(p.to_ir(), until="score").stages["score"]


def test_a_held_clash_is_found():
    with piece(key="C major") as p:
        s = p.section("a", bars=1)
        s.chart("Cmaj7")
        s.track("m", role=Role.MELODY).line("f5/1")  # F over E: the avoid note
    result = review(score_of(p))
    assert [f.kind for f in result.findings] == ["clash"]
    assert "a#1/m/1+0/v0" == result.findings[0].location


def test_a_passing_note_is_not_a_clash():
    with piece(key="C major") as p:
        s = p.section("a", bars=1)
        s.chart("Cmaj7")
        s.track("m", role=Role.MELODY).line("e5/8 f5 g5/4 c6/2")
    assert review(score_of(p)).findings == []


def test_chord_tones_and_tensions_are_counted_apart():
    with piece(key="C major") as p:
        s = p.section("a", bars=1)
        s.chart("Cmaj9")
        s.track("m", role=Role.MELODY).line("e5/4 d5 b4 c5")
    result = review(score_of(p))
    assert result.chord_tones == 3
    assert result.tensions == 1


def test_outside_notes_are_counted():
    with piece(key="C major") as p:
        s = p.section("a", bars=1)
        s.chart("Cmaj7")
        s.track("m", role=Role.MELODY).line("c#5/2 e5")
    assert review(score_of(p)).outside == 1


def test_a_bass_note_out_of_range_is_found():
    with piece(key="C major") as p:
        s = p.section("a", bars=1)
        s.track("b", role=Role.BASS).line("g0/1")
    assert [f.kind for f in review(score_of(p)).findings] == ["out of range"]


def test_parallel_fifths_are_found():
    with piece(key="C major") as p:
        s = p.section("a", bars=1)
        s.track("h", role=Role.HARMONY).notes([(60, 1 / 4)])
    ir = p.to_ir()
    # C-G moving to D-A
    ir.sections[0].tracks[0].content.notes = [
        Note(60, Fraction(1), offset=Fraction(0)),
        Note(67, Fraction(1), offset=Fraction(0)),
        Note(62, Fraction(1), offset=Fraction(1)),
        Note(69, Fraction(1), offset=Fraction(1)),
    ]
    module = compile_piece(ir, until="score").stages["score"]
    assert [f.kind for f in review(module).findings] == ["parallel"]


def test_the_chord_timeline_survives_into_the_score():
    with piece(key="C major") as p:
        s = p.section("a", bars=2)
        s.chart("Dm7 G7 | Cmaj7")
        s.track("k", role=Role.HARMONY).pattern(hits(cell="x..."))
    top = next(iter(score_of(p).body.block.ops))
    assert isinstance(top, score.ScoreOp)
    assert [c.at.data for c in top.chords()] == [0, 2, 4]


class TestSoloLine:
    def line(self, rest=0.1):
        with piece(key="D dorian") as p:
            s = p.section("solo", bars=16)
            s.chart("Dm9 | G13 | Bbmaj7 | A7alt")
            s.track("lead", role=Role.MELODY).pattern(solo_line(low=62, high=86, rest=rest))
        top = next(iter(score_of(p).body.block.ops))
        return [n for b in top.parts()[0].bars() for n in b.notes()]

    def test_stays_in_range(self):
        pitches = [midi_of(n.pitch.data) for n in self.line()]
        assert pitches and min(pitches) >= 62 and max(pitches) <= 86

    def test_never_sits_on_one_note(self):
        pitches = [midi_of(n.pitch.data) for n in self.line()]
        repeats = sum(a == b for a, b in zip(pitches, pitches[1:], strict=False))
        assert repeats < len(pitches) * 0.05

    def test_plays_in_phrases(self):
        notes = self.line(rest=0.3)
        beats_played = len(notes) / 2
        assert beats_played < 16 * 4 * 0.9

    def test_is_repeatable(self):
        assert [n.pitch.data for n in self.line()] == [n.pitch.data for n in self.line()]


def test_walking_bass_and_comp_pass_their_own_review():
    with piece(tempo=160, key="C major") as p:
        s = p.section("a", bars=8)
        s.chart("Dm9 | G13 | Cmaj9 | Em7 A7alt")
        s.track("b", role=Role.BASS).pattern(walking_bass)
        s.track("k", role=Role.HARMONY).pattern(comp).voicing("rootless", 52, 72)
    kinds = {f.kind for f in review(score_of(p)).findings}
    assert "out of range" not in kinds
