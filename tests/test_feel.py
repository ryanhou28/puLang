"""
Feel: where each player sits against the beat, how a line breathes, how loud a section is.

These are performance passes on the event stream. The promise under test is that
each does what a player would mean by it and nothing else: a laid-back bass is late
by the same amount everywhere, a legato line keeps its rests, and a swell builds
from one level to the other across its section.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from pypulang import IV, I, Role, piece, root_quarters
from pypulang.compiler import compile_piece
from pypulang.compiler.passes.lower_event import PPQ
from pypulang.compiler.passes.perform import Dynamics, Humanize, LayBack, Legato, Phrasing

F = Fraction


def song():
    with piece(tempo=100, key="C major", title="feel") as p:
        a = p.section("a", bars=2)
        a.harmony(I, IV)
        a.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
        # Two phrases: a rise to G5 and away, then after a rest a falling one
        a.track("lead", role=Role.MELODY).line("c5/8 e5 g5/4 e5/8 d5 r/4 | a5/8 g5 f5 e5 d5/2")
        b = p.section("b", bars=2)
        b.harmony(I, IV)
        b.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
        p.form([a, b])
    return p.to_ir()


def notes(passes, track):
    module = compile_piece(song(), until="event", event_passes=passes).stages["event"]
    stream = next(iter(module.body.block.ops))
    found = next(t for t in stream.tracks() if t.track.data == track).notes()
    return sorted(
        ((n.start.data, n.dur.data, n.pitch.value.data, n.vel.value.data) for n in found),
        key=lambda n: (n[0], n[2]),
    )


class TestLayBack:
    def test_a_track_moves_late_by_the_same_amount_everywhere(self):
        plain = notes([], "bass")
        late = notes([LayBack(ticks=24, tracks=("bass",))], "bass")
        assert [n[0] - p[0] for n, p in zip(late, plain, strict=True)] == [F(24, PPQ)] * len(plain)
        assert [n[1] for n in late] == [p[1] for p in plain]

    def test_negative_pushes_ahead_but_never_before_the_start(self):
        ahead = notes([LayBack(ticks=-30, tracks=("bass",))], "bass")
        assert ahead[0][0] == 0 and ahead[1][0] == 1 - F(30, PPQ)

    def test_other_tracks_stay_put(self):
        assert notes([LayBack(ticks=24, tracks=("bass",))], "lead") == notes([], "lead")


class TestPhrasing:
    def test_a_phrase_rises_to_its_highest_note_and_lets_go(self):
        shaped = [n[3] for n in notes([Phrasing(depth=14, ending=8, tracks=("lead",))], "lead")]
        first = shaped[:5]  # c e g e d: g is the peak
        assert first[2] == max(first)
        assert first[0] < first[1] < first[2] and first[2] > first[3] > first[4]

    def test_the_rest_starts_a_new_phrase_whose_peak_is_its_first_note(self):
        shaped = [n[3] for n in notes([Phrasing(tracks=("lead",))], "lead")]
        second = shaped[5:]  # a g f e d, falling from the top
        assert second[0] == max(second) and second == sorted(second, reverse=True)

    def test_a_phrase_ends_softer_than_it_began(self):
        shaped = [n[3] for n in notes([Phrasing(tracks=("lead",))], "lead")]
        assert shaped[4] < shaped[0]


class TestLegato:
    def test_notes_are_held_into_the_next_and_rests_stay_rests(self):
        joined = notes([Legato(overlap=10, tracks=("lead",))], "lead")
        starts = [n[0] for n in joined]
        ends = [n[0] + n[1] for n in joined]
        # each of the first four reaches the next note, ten ticks in
        assert all(ends[i] == starts[i + 1] + F(10, PPQ) for i in range(4))
        # the d before the rest is not stretched across it
        assert ends[4] == F(3)

    def test_a_repeated_pitch_never_overlaps_itself(self):
        with piece(tempo=100, key="C major") as p:
            a = p.section("a", bars=1)
            a.track("lead", role=Role.MELODY).line("c5/8 c5 c5/4 d5/2")
            p.form([a])
        module = compile_piece(p.to_ir(), until="event", event_passes=[Legato()]).stages["event"]
        line = sorted(
            next(iter(module.body.block.ops)).tracks()[0].notes(), key=lambda n: n.start.data
        )
        assert [n.start.data + n.dur.data for n in line[:2]] == [
            line[1].start.data,
            line[2].start.data,
        ]


class TestDynamics:
    def test_mf_leaves_velocities_as_written_and_p_softens_them(self):
        assert notes([Dynamics(marks=(("a", "mf"),))], "bass") == notes([], "bass")
        soft = notes([Dynamics(marks=(("a", "p"),))], "bass")
        plain = notes([], "bass")
        assert soft[0][3] == round(plain[0][3] * F(7, 10))
        assert soft[-1] == plain[-1]  # section b has no mark

    def test_a_swell_builds_across_its_section(self):
        swelled = [n[3] for n in notes([Dynamics(marks=(("b", "p<f"),))], "bass")][8:]
        assert swelled == sorted(swelled) and swelled[0] < swelled[-1]

    @pytest.mark.parametrize("mark", ["loud", "p<p", "f<p", "p>f"])
    def test_a_mark_that_is_not_a_dynamic_is_refused(self, mark):
        with pytest.raises(ValueError):
            notes([Dynamics(marks=(("a", mark),))], "bass")

    def test_feel_passes_compose_with_humanize(self):
        passes = [Dynamics(marks=(("a", "p<f"),)), Phrasing(tracks=("lead",)), Humanize(seed="x")]
        assert notes(passes, "lead") == notes(passes, "lead")
