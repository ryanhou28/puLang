"""Voicing strategies and the voice-lead pass."""

from __future__ import annotations

import itertools
from fractions import Fraction

import pytest

from pypulang import I, Role, comp, grid, hits, piece, riff, walking_bass
from pypulang.compiler import compile_piece, make_context, parse_ir, print_ir
from pypulang.compiler.dialects import event, score
from pypulang.compiler.frontend import import_piece
from pypulang.compiler.passes.lower_intent import LowerIntentToScore
from pypulang.compiler.passes.voice_lead import VoiceLead
from pypulang.harmony import chord_shape, parse_chord_symbol
from pypulang.ir.intent import Key
from pypulang.pitches import C3, C5, E3, G5
from pypulang.voicing import (
    STRATEGIES,
    Register,
    candidates_for,
    lead_voices,
    motion,
    total_motion,
)

C = Key("C", "major")
REGISTER = Register(50, 74)


def classes(pitches):
    return {p % 12 for p in pitches}


def chord(symbol):
    return parse_chord_symbol(symbol, C)


class TestStrategies:
    @pytest.mark.parametrize("name", sorted(STRATEGIES))
    @pytest.mark.parametrize(
        "symbol", ["Cmaj7", "Dm9", "G13", "G7alt", "Bm7b5", "Fmaj9#11", "Gsus4"]
    )
    def test_every_candidate_fits_the_register(self, name, symbol):
        candidates = candidates_for(name, chord(symbol), C, Register(40, 88))
        assert candidates, f"{name} produced nothing for {symbol}"
        for voicing in candidates:
            assert voicing == sorted(voicing)
            assert 40 <= voicing[0] and voicing[-1] <= 88

    def test_rootless_leaves_out_the_root_and_keeps_the_guide_tones(self):
        for voicing in candidates_for("rootless", chord("Dm9"), C, REGISTER):
            assert 2 not in classes(voicing)
            assert {5, 0} <= classes(voicing)  # F and C, the third and seventh

    def test_rootless_dominant_uses_the_thirteenth_for_the_fifth(self):
        for voicing in candidates_for("rootless", chord("G13"), C, REGISTER):
            assert {11, 5, 4} <= classes(voicing)  # third, seventh, thirteenth
            assert 2 not in classes(voicing) or 9 in classes(voicing)

    def test_altered_dominant_carries_its_alterations(self):
        for voicing in candidates_for("rootless", chord("G7alt"), C, REGISTER):
            assert {11, 5} <= classes(voicing)
            assert classes(voicing) & {8, 10}  # b9 or #9

    def test_drop2_spreads_wider_than_an_octave(self):
        voicings = candidates_for("drop2", chord("Cmaj7"), C, Register(48, 84))
        assert voicings
        assert all(v[-1] - v[0] > 12 for v in voicings)

    def test_quartal_stacks_fourths(self):
        key = Key("D", "dorian")
        for voicing in candidates_for(
            "quartal", parse_chord_symbol("Dm7", key), key, Register(50, 84)
        ):
            assert all(b - a in (5, 6) for a, b in zip(voicing, voicing[1:], strict=False))

    def test_upper_structure_on_alt_is_the_flat_six_triad(self):
        # G7alt: Eb major over the guide tones
        for voicing in candidates_for("upper_structure", chord("G7alt"), C, Register(48, 84)):
            assert {3, 7, 10} <= classes(voicing)

    def test_wide_keeps_the_root_at_the_bottom(self):
        for voicing in candidates_for("wide", chord("Fmaj9"), C, Register(41, 91)):
            assert voicing[0] % 12 == 5

    def test_slash_bass_sits_under_the_voicing(self):
        for voicing in candidates_for("close", chord("Fmaj7/A"), C, REGISTER):
            assert voicing[0] % 12 == 9

    def test_unknown_strategy_names_the_ones_that_exist(self):
        with pytest.raises(KeyError, match="rootless"):
            candidates_for("nope", chord("C"), C, REGISTER)


class TestVoiceLeading:
    CHART = ["Dm9", "G13", "Cmaj9", "A7alt", "Dm9", "G7alt", "Cmaj9", "Fmaj9#11"]

    def options(self, name="rootless"):
        return [candidates_for(name, chord(s), C, REGISTER) for s in self.CHART]

    def test_chooses_one_voicing_from_each_chords_candidates(self):
        options = self.options()
        chosen = lead_voices(options, REGISTER)
        assert len(chosen) == len(self.CHART)
        assert all(v in o for v, o in zip(chosen, options, strict=True))

    def test_finds_the_true_minimum_motion(self):
        options = self.options()
        led = total_motion(lead_voices(options, REGISTER))
        best = min(total_motion(list(path)) for path in itertools.product(*options))
        assert led == best

    def test_is_the_textbook_rootless_two_five_one(self):
        options = [
            candidates_for("rootless", chord(s), C, REGISTER) for s in ("Dm9", "G13", "Cmaj9")
        ]
        first, second, third = lead_voices(options, REGISTER)
        assert first == [60, 64, 65, 69]  # C E F A
        assert second == [59, 64, 65, 69]  # B E F A: only the seventh resolves
        assert third == [59, 62, 64, 67]  # B D E G

    def test_moves_no_more_than_the_best_greedy_path(self):
        options = self.options()
        led = lead_voices(options, REGISTER)
        greedy = [options[0][0]]
        for choices in options[1:]:
            greedy.append(min(choices, key=lambda v: motion(greedy[-1], v)))
        assert total_motion(led) <= total_motion(greedy)

    def test_is_repeatable(self):
        assert lead_voices(self.options(), REGISTER) == lead_voices(self.options(), REGISTER)

    def test_keeps_a_common_tone_when_it_can(self):
        options = [candidates_for("close", chord(s), C, REGISTER) for s in ("C", "Am")]
        first, second = lead_voices(options, REGISTER)
        assert set(first) & set(second)


def compiled_part(p, name, stage="score"):
    module = compile_piece(p.to_ir(), until=stage).stages[stage]
    top = next(iter(module.body.block.ops))
    if stage == "score":
        return next(x for x in top.parts() if x.part.data == name)
    return next(x for x in top.tracks() if x.track.data == name)


class TestThroughThePipeline:
    def song(self):
        with piece(tempo=120, key="C major") as p:
            s = p.section("a", bars=4)
            s.chart("Dm9 G13 | Cmaj9 | Em7 A7b13 | Dm9 G7alt")
            s.track("keys", role=Role.HARMONY).pattern(hits(cell="x-------", step=1 / 8)).voicing(
                "rootless", E3, C5
            )
            s.track("plain", role=Role.HARMONY).pattern(hits(cell="x-------", step=1 / 8))
        return p

    def test_voicing_reaches_the_notes(self):
        bars = compiled_part(self.song(), "keys").bars()
        first_chord = [n for n in bars[0].notes() if n.beat.data == 0]
        assert len(first_chord) == 4

    def test_a_track_with_no_voicing_stays_close_position(self):
        result = compile_piece(self.song().to_ir(), until="score")
        keys, plain = next(iter(result.stages["score"].body.block.ops)).parts()
        assert keys.bars()[0].notes()[0].pitch.data != plain.bars()[0].notes()[0].pitch.data

    def test_slots_are_visible_in_the_ir_before_they_become_notes(self):
        ctx = make_context()
        module = import_piece(self.song().to_ir())
        LowerIntentToScore().apply(ctx, module)
        VoiceLead().apply(ctx, module)
        module.verify()
        text = print_ir(module)
        assert "score.slot" in text and "rootless" in text
        assert isinstance(next(iter(module.body.block.ops)), score.ScoreOp)
        assert print_ir(parse_ir(text)) == text


class TestPatterns:
    def test_grid_keeps_its_place_across_chord_changes(self):
        with piece() as p:
            s = p.section("a", bars=2)
            s.chart("C F | G C")
            s.track("k", role=Role.RHYTHM).pattern(grid(cell="x...x...x...x...", pitch=36))
        notes = compiled_part(p, "k", "event").notes()
        assert [n.start.data for n in notes] == [Fraction(i) for i in range(8)]

    def test_grid_loops_a_two_bar_cell(self):
        with piece() as p:
            s = p.section("a", bars=4)
            s.track("k", role=Role.RHYTHM).pattern(
                grid(cell="x... .... .... .... .... .... .... x...", pitch=36)
            )
        starts = [n.start.data for n in compiled_part(p, "k", "event").notes()]
        assert starts == [0, 7, 8, 15]

    def test_grid_works_in_seven_eight(self):
        with piece(time_sig="7/8") as p:
            s = p.section("a", bars=2)
            s.track("k", role=Role.RHYTHM).pattern(grid(cell="x.x.x..", step=1 / 8, pitch=36))
        starts = [n.start.data for n in compiled_part(p, "k", "event").notes()]
        assert starts == [0, 1, 2, Fraction(7, 2), Fraction(9, 2), Fraction(11, 2)]

    def test_hits_hold_for_their_dashes(self):
        with piece() as p:
            s = p.section("a", bars=1)
            s.harmony(I)
            s.track("k", role=Role.HARMONY).pattern(hits(cell="x--.x...", step=1 / 8))
        notes = compiled_part(p, "k", "event").notes()
        assert {n.dur.data for n in notes if n.start.data == 0} == {Fraction(3, 2)}

    def test_riff_follows_the_changes(self):
        with piece() as p:
            s = p.section("a", bars=2)
            s.chart("Cmaj7 | Am7")
            s.track("b", role=Role.BASS).pattern(
                riff(cell="x...x...x...x...", degrees="1 3 5 7", base=48)
            )
        pitches = [n.pitch.value.data for n in compiled_part(p, "b", "event").notes()]
        assert pitches[:4] == [48, 52, 55, 59]  # C E G B
        assert pitches[4:] == [45, 48, 52, 55]  # A C E G: the third follows the chord

    def test_walking_bass_lands_on_each_root(self):
        with piece() as p:
            s = p.section("a", bars=4)
            s.chart("Dm7 | G7 | Cmaj7 | A7")
            s.track("b", role=Role.BASS).pattern(walking_bass)
        notes = compiled_part(p, "b", "event").notes()
        assert len(notes) == 16
        roots = [n.pitch.value.data % 12 for n in notes if n.start.data % 4 == 0]
        assert roots == [2, 7, 0, 9]
        assert all(28 <= n.pitch.value.data <= 55 for n in notes)

    def test_walking_bass_approaches_the_next_root_by_step_or_fifth(self):
        with piece() as p:
            s = p.section("a", bars=2)
            s.chart("Dm7 | G7")
            s.track("b", role=Role.BASS).pattern(walking_bass)
        notes = compiled_part(p, "b", "event").notes()
        last = notes[3].pitch.value.data
        target = notes[4].pitch.value.data
        assert abs(last - target) % 12 in (1, 11, 5, 7)

    def test_comp_is_repeatable_and_changes_bar_to_bar(self):
        def make():
            with piece() as p:
                s = p.section("a", bars=8)
                s.chart("Dm9 | G13 | Cmaj9 | Cmaj9")
                s.track("k", role=Role.HARMONY).pattern(comp(density=0.8)).voicing(
                    "rootless", C3, G5
                )
            return compiled_part(p, "k", "event").notes()

        first = [(n.pitch.value.data, n.start.data) for n in make()]
        assert first == [(n.pitch.value.data, n.start.data) for n in make()]
        by_bar = {}
        for _, start in first:
            by_bar.setdefault(int(start // 4), set()).add(start % 4)
        assert len({frozenset(v) for v in by_bar.values()}) > 1


class TestChartAndLine:
    def test_chart_loops_to_fill_the_section(self):
        with piece(key="C major") as p:
            s = p.section("a", bars=8)
            s.chart("Dm7 G7 | Cmaj7")
        changes = p.to_ir().sections[0].harmony.changes
        assert len(changes) == 12
        assert sum(c.duration for c in changes) == 8

    def test_line_reads_values_and_carries_them_over(self):
        with piece() as p:
            s = p.section("a", bars=1)
            s.track("m", role=Role.MELODY).line("c5/8 d5 e5/4 g5/2")
        notes = p.to_ir().sections[0].tracks[0].content.notes
        assert [n.offset for n in notes] == [0, Fraction(1, 2), 1, 2]
        assert [n.pitch for n in notes] == [72, 74, 76, 79]

    def test_line_rejects_a_bar_that_does_not_add_up(self):
        with piece() as p:
            s = p.section("a", bars=2)
            with pytest.raises(ValueError, match="holds"):
                s.track("m", role=Role.MELODY).line("c5/4 d5 e5 | f5/1")

    def test_line_ties_triplets_and_ghosts(self):
        with piece() as p:
            s = p.section("a", bars=1)
            s.track("m", role=Role.MELODY).line("c5/4t d5 e5 g5/2~ g5/4 a5?")
        notes = p.to_ir().sections[0].tracks[0].content.notes
        assert [n.duration for n in notes][:3] == [Fraction(2, 3)] * 3
        assert notes[3].duration == 3
        assert notes[4].velocity < notes[0].velocity


def test_chord_shape_names_its_tones():
    shape = chord_shape(chord("G13"), C)
    assert shape.root == 7
    assert shape.third.interval == 4
    assert shape.seventh.interval == 10
    assert [t.function for t in shape.colours()][:2] == ["9", "13"]


def test_the_stream_has_no_note_before_zero():
    with piece() as p:
        s = p.section("a", bars=1)
        s.harmony(I)
        s.track("k", role=Role.HARMONY).pattern(comp)
    module = compile_piece(p.to_ir(), until="event").stages["event"]
    stream = next(iter(module.body.block.ops))
    assert isinstance(stream, event.StreamOp)
    assert all(n.start.data >= 0 for t in stream.tracks() for n in t.notes())
