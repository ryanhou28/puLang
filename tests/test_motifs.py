"""
Melodies made of motifs.

The promise under test: a motif written once in scale degrees comes out as the
notes it names in the section's key, its developments do what music theory means
by them, a held note does not clash with the chord under it, and an edit to a
motif reaches every place that uses it.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from pypulang import IV, I, Role, V, piece
from pypulang.compiler import compile_piece
from pypulang.compiler.edits import Edit
from pypulang.compiler.passes.intent_passes import Transpose
from pypulang.ir.intent import Chord, Key, Piece
from pypulang.lift import daw_notes
from pypulang.motifs import develop, parse_motif, parse_phrase, realize

C = Key("C", "major")
A_MINOR = Key("A", "minor")
F = Fraction


def steps(motif) -> list[int]:
    return [n.step for n in motif.notes]


def pitches(notes) -> list[int]:
    return [n.pitch for n in notes]


class TestMotifText:
    def test_degrees_values_and_rests(self):
        m = parse_motif("1/8 2 3/4 r/8 5/4.")
        assert steps(m) == [0, 1, 2, 4]
        assert [n.start for n in m.notes] == [0, F(1, 2), 1, F(5, 2)]
        assert [n.dur for n in m.notes] == [F(1, 2), F(1, 2), 1, F(3, 2)]
        assert m.length == 4

    def test_octaves_and_accidentals(self):
        m = parse_motif("1' 5, b7 #4")
        assert steps(m) == [7, -3, 6, 3]
        assert [n.accidental for n in m.notes] == [0, 0, -1, 1]

    def test_ties_accents_ghosts_and_staccato(self):
        m = parse_motif("3/4~ 3/8 5> 6? 1'!")
        assert m.notes[0].dur == F(3, 2)
        assert [n.velocity_scale for n in m.notes[1:]] == [F(6, 5), F(1, 2), 1]
        assert m.notes[-1].articulation == "staccato"

    def test_a_mistake_is_named(self):
        with pytest.raises(ValueError, match="'8x'"):
            parse_motif("1/4 8x")


class TestDevelopment:
    hook = parse_motif("5/8 6 1'/4 7/8 5/4.")

    def test_a_sequence_moves_by_scale_steps(self):
        assert steps(develop(self.hook, "+", "1")) == [5, 6, 8, 7, 5]
        assert steps(develop(self.hook, "-", "2")) == [2, 3, 5, 4, 2]

    def test_inversion_mirrors_around_the_first_note(self):
        assert steps(develop(self.hook, "inv", None)) == [4, 3, 1, 2, 4]

    def test_retrograde_keeps_the_rhythm_backwards(self):
        rev = develop(self.hook, "rev", None)
        assert steps(rev) == [4, 6, 7, 5, 4]
        assert [n.dur for n in rev.notes] == [F(3, 2), F(1, 2), 1, F(1, 2), F(1, 2)]
        assert rev.notes[0].start == 0 and rev.length == self.hook.length

    def test_augmentation_and_diminution(self):
        assert develop(self.hook, "x", "2").length == 2 * self.hook.length
        assert develop(self.hook, "x", "1/2").notes[1].start == F(1, 4)

    def test_fragments(self):
        assert steps(develop(self.hook, "first", "2")) == [4, 5]
        last = develop(self.hook, "last", "2")
        assert steps(last) == [6, 4] and last.notes[0].start == 0

    def test_a_motif_that_starts_with_a_rest_keeps_it_when_cut(self):
        m = parse_motif("r/8 3 5 1'/4")
        assert develop(m, "first", "2").notes[0].start == F(1, 2)

    def test_end_lands_on_the_nearest_octave_of_a_degree(self):
        assert steps(develop(self.hook, "end", "1"))[-1] == 7  # 1' is nearer to 5 than 1 is
        assert steps(develop(self.hook, "end", "3"))[-1] == 2

    def test_vary_is_the_same_for_the_same_seed_and_differs_for_another(self):
        long = parse_motif("1/2 3 5 1'")
        once = develop(long, "vary", "1", seed_text="x")
        assert once == develop(long, "vary", "1", seed_text="x")
        assert len(once.notes) > len(long.notes)
        others = {steps(develop(long, "vary", str(s), seed_text="x")).__repr__() for s in range(8)}
        assert len(others) > 1

    def test_anticipation(self):
        early = develop(self.hook, "early", "8")
        assert early.notes[0].start == F(-1, 2) and early.length == self.hook.length


class TestPhrase:
    def test_placements_and_developments(self):
        p = parse_phrase("hook; hook +2 inv; rest 2; tail x1/2 end 1")
        assert [x.motif for x in p] == ["hook", "hook", None, "tail"]
        assert p[1].ops == (("+", "2"), ("inv", None))
        assert p[2].rest == 2
        assert p[3].ops == (("x", "1/2"), ("end", "1"))

    @pytest.mark.parametrize("text", ["hook +", "hook wobble", "hook end", "rest"])
    def test_a_mistake_is_refused(self, text):
        with pytest.raises(ValueError):
            parse_phrase(text)


def spans(*chords: tuple[str, int]) -> list[tuple[Chord, F, F]]:
    result, at = [], F(0)
    for numeral, beats in chords:
        result.append((Chord(numeral), at, F(beats)))
        at += beats
    return result


class TestRealize:
    def test_the_first_placement_is_written_from_the_tonic_nearest_the_middle(self):
        notes = realize("m", {"m": "5,/4 1 5"}, C, [], F(4), fit=False, low=55, high=79)
        assert pitches(notes) == [67, 72, 79]  # the middle is 67; its nearest C is C5

    def test_degrees_are_read_in_the_key(self):
        notes = realize("m", {"m": "1/4 3 5"}, A_MINOR, [], F(4), fit=False, low=57, high=80)
        assert pitches(notes) == [69, 72, 76]  # A C E

    def test_placements_follow_each_other_in_time(self):
        notes = realize("m; rest 2; m", {"m": "1/4 2"}, C, [], F(4), fit=False)
        assert [n.start for n in notes] == [0, 1, 4, 5]

    def test_each_placement_starts_near_where_the_line_is(self):
        notes = realize("m; m +4", {"m": "1/4 2 3"}, C, [], F(4), fit=False, low=55, high=88)
        assert pitches(notes)[3] - pitches(notes)[2] == 3  # E up to G, not down to G below

    def test_a_sequence_a_step_past_the_top_stays_put(self):
        notes = realize("m; m +1", {"m": "1/4 3 5"}, C, [], F(4), fit=False, low=60, high=67)
        assert pitches(notes) == [60, 64, 67, 62, 65, 69]

    def test_one_climbing_far_past_the_top_drops_an_octave(self):
        notes = realize("m; m +4", {"m": "1/4 3 5"}, C, [], F(4), fit=False, low=55, high=69)
        assert pitches(notes) == [60, 64, 67, 55, 59, 62]

    def test_a_held_avoid_note_moves_onto_the_chord(self):
        # F held over C major is a semitone above E: it resolves down to E
        notes = realize("m", {"m": "4/2 2"}, C, spans(("I", 4)), F(4), low=52, high=72)
        assert pitches(notes) == [64, 62]

    def test_tensions_are_kept(self):
        # D over C is a 9th and A a 13th: neither is a semitone above a chord tone
        notes = realize("m", {"m": "2/2 6"}, C, spans(("I", 4)), F(4), low=52, high=72)
        assert pitches(notes) == [62, 69]

    def test_passing_notes_off_the_beat_are_left_alone(self):
        notes = realize("m", {"m": "3/8 4 5/2"}, C, spans(("I", 4)), F(4), low=52, high=72)
        assert pitches(notes) == [64, 65, 67]

    def test_without_fit_nothing_moves(self):
        notes = realize("m", {"m": "4/2"}, C, spans(("I", 4)), F(4), fit=False, low=52, high=72)
        assert pitches(notes) == [65]

    def test_an_undefined_motif_is_named(self):
        with pytest.raises(ValueError, match="'nope'"):
            realize("nope", {}, C, [], F(4))


def song(phrase: str = "hook; hook +1; hook end 1", key: str = "C major") -> Piece:
    with piece(tempo=100, key=key, title="motifs") as p:
        p.motif("hook", "5/8 6 1'/4 7/8 5/4. r/8")
        p.motif("tail", "3/4 2 1/2")
        a = p.section("a", bars=4)
        a.harmony(I, IV, V, I)
        a.track("lead", role=Role.MELODY).melody(phrase, low=64, high=84)
        p.form([a, a])
    return p.to_ir()


def lead(result, tag: str = "a#1") -> list[int]:
    notes = daw_notes(result.daw)
    return [
        n[0]
        for loc, n in sorted(notes.items(), key=lambda kv: kv[1][1])
        if loc.startswith(f"{tag}/lead/")
    ]


class TestCompile:
    def test_a_melody_compiles_to_notes_in_every_occurrence(self):
        result = compile_piece(song())
        assert lead(result, "a#1") == lead(result, "a#2")
        assert len(lead(result)) == 15

    def test_the_melody_follows_a_transposition(self):
        plain = lead(compile_piece(song()))
        moved = lead(compile_piece(song(), intent_passes=[Transpose(semitones=2)]))
        assert moved == [p + 2 for p in plain]

    def test_a_phrase_longer_than_its_section_stops_at_its_end(self):
        result = compile_piece(song("hook; hook; hook; hook; hook"))
        last = max(
            n[1] + n[2] for loc, n in daw_notes(result.daw).items() if loc.startswith("a#1/")
        )
        assert last <= 16 * 960

    def test_an_undefined_motif_names_the_track(self):
        with pytest.raises(ValueError, match="a/lead: No motif called 'bridge'"):
            compile_piece(song("bridge"))

    def test_a_mistake_in_the_dsl_is_reported_where_it_is_written(self):
        with pytest.raises(ValueError):
            with piece() as p:
                p.motif("hook", "1/4 9")


class TestEdits:
    def test_a_motif_edit_changes_every_place_that_uses_it(self):
        before = lead(compile_piece(song()))
        edit = Edit(
            "intent", "motif/hook", "notes", "1/8 2 3/4 2/8 1/4. r/8", "5/8 6 1'/4 7/8 5/4. r/8"
        )
        result = compile_piece(song(), edits=[edit])
        assert result.edits.applied == [edit.key] and not result.edits.stale
        after = lead(result)
        assert after != before and len(after) == len(before)
        assert lead(result, "a#2") == after

    def test_a_melody_edit_changes_the_phrase(self):
        edit = Edit("intent", "a/lead", "melody", "tail; tail -1", "hook; hook +1; hook end 1")
        result = compile_piece(song(), edits=[edit])
        assert result.edits.applied == [edit.key]
        assert len(lead(result)) == 6

    def test_an_edit_to_a_missing_motif_is_orphaned(self):
        result = compile_piece(song(), edits=[Edit("intent", "motif/gone", "notes", "1", "1")])
        assert result.edits.orphaned and not result.edits.applied


class TestInspector:
    def test_a_melody_track_shows_its_phrase_and_the_motifs_it_uses(self):
        from pypulang.backends.kaidaw.state import Lock, Overrides
        from pypulang.inspector import Model

        model = Model(compile_piece(song(), keep_trace=True), Lock(), Overrides())
        info = model.track("a", "lead")
        assert info.plays == "melody"
        assert info.settings["melody"] == "hook; hook +1; hook end 1"
        assert info.motifs == {"hook": "5/8 6 1'/4 7/8 5/4. r/8"}  # not "tail", which it never uses
