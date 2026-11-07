"""
The DSL's note values mean what they say.

`1/4` is a quarter note. The IR counts in quarter-note beats, so the DSL converts
at the door. Before this was so, 1/4 reached the IR as a quarter of a beat: every
literal melody played four times too fast and `rate=1/16` played 64th notes.
"""

from __future__ import annotations

from fractions import Fraction

from pypulang import I, Role, arp, block_chords, four_on_floor, piece
from pypulang.midi import realize_to_events
from pypulang.pitches import C4, D4, E4, G4, chord, note, rest


def onsets(p, name: str) -> list[float]:
    events, _ = realize_to_events(p.to_ir())
    return sorted({e[1] for e in events if e[4] == name})


def test_four_quarter_notes_fill_a_bar_of_four_four():
    with piece() as p:
        s = p.section("a", bars=1)
        s.track("m", role=Role.MELODY).notes([(C4, 1 / 4), (D4, 1 / 4), (E4, 1 / 4), (G4, 1 / 4)])
    assert onsets(p, "m") == [0, 1, 2, 3]


def test_eighths_triplets_and_rests():
    with piece() as p:
        s = p.section("a", bars=1)
        s.track("m", role=Role.MELODY).notes(
            [(C4, 1 / 8), (D4, 1 / 8), rest(1 / 4), note(E4, 1 / 12), note(G4, 1 / 12), (C4, 1 / 12)]
        )
    ir = p.to_ir()
    offsets = [n.offset for n in ir.sections[0].tracks[0].content.notes]
    assert offsets == [
        Fraction(0),
        Fraction(1, 2),
        Fraction(1),
        Fraction(2),
        Fraction(7, 3),
        Fraction(8, 3),
    ]


def test_chord_duration_is_a_note_value():
    with piece() as p:
        s = p.section("a", bars=1)
        s.track("m", role=Role.HARMONY).notes([chord([C4, E4], 1 / 2), (G4, 1 / 2)])
    assert onsets(p, "m") == [0, 2]


def test_sixteenth_rate_is_four_notes_per_beat():
    with piece() as p:
        s = p.section("a", bars=1)
        s.harmony(I)
        s.track("k", role=Role.HARMONY).pattern(arp("up"), rate=1 / 16)
    assert len(onsets(p, "k")) == 16


def test_half_note_block_chords():
    with piece() as p:
        s = p.section("a", bars=1)
        s.harmony(I)
        s.track("k", role=Role.HARMONY).pattern(block_chords, rate=1 / 2)
    assert onsets(p, "k") == [0, 2]


def test_default_arp_is_eighth_notes():
    with piece() as p:
        s = p.section("a", bars=1)
        s.harmony(I)
        s.track("k", role=Role.HARMONY).pattern(arp("up"))
    assert len(onsets(p, "k")) == 8


def test_default_hihat_is_eighth_notes():
    with piece() as p:
        s = p.section("a", bars=1)
        s.harmony(I)
        s.track("d", role=Role.RHYTHM).pattern(four_on_floor)
    assert onsets(p, "d") == [i / 2 for i in range(8)]
