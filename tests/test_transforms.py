"""Harmony transforms and performance passes."""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pypulang import IV, V, I, Role, ii, grid, hits, piece, root_quarters, vi
from pypulang.compiler import compile_piece
from pypulang.compiler.dialects import event
from pypulang.compiler.locs import loc_key
from pypulang.compiler.passes.intent_passes import Reharmonize, Transpose
from pypulang.compiler.passes.perform import Accent, Humanize, Pump, Swing, swing_time
from pypulang.harmony import chord_symbol, parse_chord_symbol, root_pitch_class
from pypulang.ir.intent import ChordChange, Key
from pypulang.reharm import (
    is_dominant,
    jazzify,
    modal_interchange,
    reharmonize,
    secondary_dominants,
    transposed_key,
    tritone_sub,
)

C = Key("C", "major")


def chord(symbol, key=C):
    return parse_chord_symbol(symbol, key)


def notes_of(module, track):
    stream = next(iter(module.body.block.ops))
    return next(t for t in stream.tracks() if t.track.data == track).notes()


class TestReharm:
    def test_tritone_sub_moves_a_dominant_six_semitones(self):
        sub = tritone_sub(chord("G7"), C)
        assert root_pitch_class(sub, C) == 1
        assert chord_symbol(sub, C) == "Db7"

    def test_tritone_sub_leaves_other_chords_alone(self):
        assert tritone_sub(chord("Dm7"), C) == chord("Dm7")
        assert tritone_sub(chord("Cmaj7"), C) == chord("Cmaj7")

    def test_jazzify_adds_the_diatonic_seventh(self):
        assert chord_symbol(jazzify(chord("C"), C), C) == "Cmaj7"
        assert chord_symbol(jazzify(chord("Dm"), C), C) == "Dm7"
        assert chord_symbol(jazzify(chord("G"), C), C) == "G7"
        assert chord_symbol(jazzify(chord("Dm7"), C), C) == "Dm79"

    def test_modal_interchange_borrows_from_the_parallel_minor(self):
        assert chord_symbol(modal_interchange(chord("F"), C), C) == "Fm"
        assert chord_symbol(modal_interchange(chord("Am"), C), C) == "Ab"

    def test_secondary_dominants_prepare_each_target(self):
        changes = [
            ChordChange(chord("C"), Fraction(1)),
            ChordChange(chord("Dm"), Fraction(1)),
            ChordChange(chord("G7"), Fraction(1)),
            ChordChange(chord("C"), Fraction(1)),
        ]
        result = secondary_dominants(changes, C)
        names = [chord_symbol(c.chord, C) for c in result]
        assert names[:3] == ["C", "A7", "Dm"]
        assert sum(c.duration for c in result) == 4

    def test_unknown_strategy_lists_the_real_ones(self):
        with pytest.raises(KeyError, match="tritone_sub"):
            reharmonize([], C, "nonsense")

    def test_is_dominant(self):
        assert is_dominant(chord("G13"))
        assert is_dominant(chord("G7alt"))
        assert not is_dominant(chord("Gmaj7"))
        assert not is_dominant(chord("Gm7"))


class TestPassesReachEveryTrack:
    def song(self):
        with piece(tempo=120, key="C major") as p:
            s = p.section("a", bars=2)
            s.chart("Dm7 G7 | Cmaj7")
            s.track("bass", role=Role.BASS).pattern(root_quarters)
            s.track("keys", role=Role.HARMONY).pattern(hits(cell="x.", step=1 / 4))
        return p.to_ir()

    def test_one_harmony_rewrite_changes_every_track_that_follows_it(self):
        plain = compile_piece(self.song(), until="event").stages["event"]
        subbed = compile_piece(
            self.song(), until="event", intent_passes=[Reharmonize("tritone_sub")]
        ).stages["event"]
        for track in ("bass", "keys"):
            before = [n.pitch.value.data for n in notes_of(plain, track)]
            after = [n.pitch.value.data for n in notes_of(subbed, track)]
            assert before != after

    def test_transpose_moves_chords_and_literal_notes_together(self):
        with piece(tempo=120, key="C major") as p:
            s = p.section("a", bars=1)
            s.chart("Cmaj7")
            s.track("keys", role=Role.HARMONY).pattern(hits(cell="x...", step=1 / 4))
            s.track("lead", role=Role.MELODY).line("c5/1")
        moved = compile_piece(p.to_ir(), until="event", intent_passes=[Transpose(2)]).stages[
            "event"
        ]
        original = compile_piece(p.to_ir(), until="event").stages["event"]
        for track in ("keys", "lead"):
            a = [n.pitch.value.data for n in notes_of(original, track)]
            b = [n.pitch.value.data for n in notes_of(moved, track)]
            assert [x + 2 for x in a] == b

    def test_transposed_key_is_spelled_as_written(self):
        assert transposed_key(Key("C", "major"), 3).root == "Eb"
        assert transposed_key(Key("D", "dorian"), 4).root == "F#"
        assert transposed_key(Key("D", "dorian"), 4).mode == "dorian"

    def test_transform_makes_a_section_that_follows_new_harmony(self):
        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, vi, ii, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters)
            chorus = verse.transform("chorus", reharmonize="jazzify", transpose=5)
            p.form([verse, chorus])
        ir = p.to_ir()
        assert [s.name for s in ir.sections] == ["verse", "chorus"]
        assert ir.sections[1].key.root == "F"
        assert len(ir.sections[1].tracks) == 1
        assert ir.sections[1].harmony.changes[0].chord.extensions == ("maj7",)

    def test_chord_extensions_from_the_dsl(self):
        with piece(key="C major") as p:
            s = p.section("a", bars=1)
            s.harmony(V.ext("7", "b9"))
        assert p.to_ir().sections[0].harmony.changes[0].chord.extensions == ("7", "b9")

    def test_iv_is_exported(self):
        assert IV.to_chord().numeral == "IV"


class TestSwing:
    def test_triplet_swing_moves_the_off_beat_to_two_thirds(self):
        assert swing_time(Fraction(1, 2), Fraction(2, 3), Fraction(1, 2)) == Fraction(2, 3)

    def test_on_beats_do_not_move(self):
        for beat in range(8):
            assert swing_time(Fraction(beat), Fraction(2, 3), Fraction(1, 2)) == beat

    @given(st.fractions(min_value=0, max_value=32, max_denominator=48))
    def test_swing_preserves_order_and_stays_in_the_beat(self, time):
        warped = swing_time(time, Fraction(2, 3), Fraction(1, 2))
        assert int(warped) == int(time)
        later = swing_time(time + Fraction(1, 96), Fraction(2, 3), Fraction(1, 2))
        assert later > warped

    def test_straight_ratio_changes_nothing(self):
        assert swing_time(Fraction(3, 8), Fraction(1, 2), Fraction(1, 2)) == Fraction(3, 8)

    def test_only_named_tracks_swing(self):
        with piece(tempo=120) as p:
            s = p.section("a", bars=1)
            s.track("a", role=Role.RHYTHM).pattern(grid(cell="x.x.x.x.", step=1 / 8))
            s.track("b", role=Role.RHYTHM).pattern(grid(cell="x.x.x.x.", step=1 / 8))
            s.track("c", role=Role.RHYTHM).pattern(grid(cell="xxxxxxxx", step=1 / 8))
        result = compile_piece(p.to_ir(), until="event", event_passes=[Swing(tracks=("c",))])
        module = result.stages["event"]
        starts = [n.start.data for n in notes_of(module, "c")]
        assert starts[1] == Fraction(2, 3)
        assert [n.start.data for n in notes_of(module, "a")] == [0, 1, 2, 3]


class TestHumanize:
    def song(self, chord_two="G7"):
        with piece(tempo=120, key="C major") as p:
            s = p.section("a", bars=2)
            s.chart(f"Cmaj7 | {chord_two}")
            s.track("keys", role=Role.HARMONY).pattern(hits(cell="x.x.", step=1 / 4))
        return p.to_ir()

    def compile(self, ir):
        passes = [Humanize(timing=20, velocity=10, seed="take1")]
        return compile_piece(ir, until="event", event_passes=passes).stages["event"]

    def test_is_repeatable(self):
        a = [(n.start.data, n.vel.value.data) for n in notes_of(self.compile(self.song()), "keys")]
        b = [(n.start.data, n.vel.value.data) for n in notes_of(self.compile(self.song()), "keys")]
        assert a == b

    def test_changing_a_chord_leaves_other_notes_exactly_where_they_were(self):
        first = {
            loc_key(n.location): (n.start.data, n.vel.value.data)
            for n in notes_of(self.compile(self.song()), "keys")
        }
        second = {
            loc_key(n.location): (n.start.data, n.vel.value.data)
            for n in notes_of(self.compile(self.song("Am7")), "keys")
        }
        assert first == second

    def test_really_moves_notes(self):
        notes = notes_of(self.compile(self.song()), "keys")
        assert any(n.start.data.denominator != 1 and n.start.data * 2 % 1 != 0 for n in notes)


class TestPump:
    def test_ducks_on_every_trigger_hit_and_recovers(self):
        with piece(tempo=120) as p:
            s = p.section("a", bars=1)
            s.track("kick", role=Role.RHYTHM).pattern(grid(cell="x...x...x...x...", pitch=36))
            s.track("pad", role=Role.HARMONY).line("c4/1")
        module = compile_piece(
            p.to_ir(), until="event", event_passes=[Pump(target="pad", trigger="kick", depth=0.5)]
        ).stages["event"]
        stream = next(iter(module.body.block.ops))
        pad = next(t for t in stream.tracks() if t.track.data == "pad")
        (curve,) = pad.curves()
        points = dict(curve.point_list())
        for beat in range(4):
            assert points[Fraction(beat)] < Fraction(1, 2)

    def test_reaches_the_daw_as_automation_on_the_fader(self):
        with piece(tempo=120) as p:
            s = p.section("a", bars=1)
            s.track("kick", role=Role.RHYTHM).pattern(grid(cell="x...", pitch=36))
            s.track("pad", role=Role.HARMONY).line("c4/1")
        module = compile_piece(p.to_ir(), event_passes=[Pump(target="pad", trigger="kick")]).daw
        project = next(iter(module.body.block.ops))
        pad = next(t for t in project.tracks() if t.track.data == "pad")
        (automation,) = pad.automations()
        assert (automation.device.data, automation.param.data) == ("mix", "volume")


def test_accent_shapes_velocity_by_beat():
    with piece(tempo=120) as p:
        s = p.section("a", bars=1)
        s.track("h", role=Role.RHYTHM).pattern(grid(cell="x.x.x.x.", step=1 / 8))
    module = compile_piece(p.to_ir(), until="event", event_passes=[Accent(on=10, off=-10)]).stages[
        "event"
    ]
    assert all(n.vel.value.data == 110 for n in notes_of(module, "h"))


def test_event_dialect_is_what_the_passes_see():
    assert event.NoteOp.name == "event.note"
