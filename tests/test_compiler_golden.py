"""
The compiler must play exactly what the original realizer played.

The pipeline replaced one function with four lowerings. These tests hold it to
that function's output, note for note, on the shipped examples and on generated
pieces, so a difference can only be a deliberate change.
"""

from __future__ import annotations

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from pypulang import (
    IV,
    I,
    Role,
    V,
    arp,
    block_chords,
    four_on_floor,
    piece,
    rock_beat,
    root_eighths,
    root_quarters,
    vi,
)
from pypulang.backends.midi import event_to_midi
from pypulang.compiler import compile_piece, parse_ir, print_ir
from pypulang.compiler.dialects import event
from pypulang.ir.intent import (
    Chord,
    ChordChange,
    Harmony,
    Key,
    Note,
    Notes,
    Pattern,
    Piece,
    Section,
    TimeSignature,
    Track,
)
from pypulang.midi import realize_to_events, realize_to_midi
from pypulang.pitches import A5, B5, D5, E5, G5, rest


def compiled_events(ir: Piece) -> list[tuple[int, float, float, int, str, str]]:
    module = compile_piece(ir, until="event").stages["event"]
    stream = next(o for o in module.body.block.ops if isinstance(o, event.StreamOp))
    return [
        (
            n.pitch.value.data,
            float(n.start.data),
            float(n.dur.data),
            n.vel.value.data,
            t.track.data,
            t.role.data,
        )
        for t in stream.tracks()
        for n in t.notes()
    ]


def assert_same_notes(ir: Piece) -> None:
    old, _ = realize_to_events(ir)
    assert sorted(compiled_events(ir)) == sorted(old)


def full_song() -> Piece:
    with piece(tempo=120, key="G major", title="Full Song") as p:
        verse = p.section("verse", bars=8)
        verse.harmony(I, vi, IV, V)
        verse.track("bass", role=Role.BASS).pattern(root_eighths).octave(-2)
        verse.track("keys", role=Role.HARMONY).pattern(arp("up"), rate=1 / 4)
        verse.track("melody", role=Role.MELODY).notes(
            [(D5, 1), (E5, 1), (G5, 2), (A5, 1), (G5, 1), (E5, 2), rest(4), (B5, 4)]
        )
        verse.track("drums", role=Role.RHYTHM).pattern(rock_beat)
        chorus = p.section("chorus", bars=8)
        chorus.harmony(IV, V, I, vi)
        chorus.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
        chorus.track("keys", role=Role.HARMONY).pattern(block_chords, rate=2)
        chorus.track("drums", role=Role.RHYTHM).pattern(four_on_floor)
        p.form([verse, chorus, verse, chorus])
    return p.to_ir()


class TestGolden:
    def test_full_song_matches_note_for_note(self):
        assert_same_notes(full_song())

    def test_midi_file_is_identical(self):
        ir = full_song()
        old = realize_to_midi(ir)
        new = event_to_midi(compile_piece(ir, until="event").stages["event"])
        assert old.ticks_per_beat == new.ticks_per_beat
        assert len(old.tracks) == len(new.tracks)
        for old_track, new_track in zip(old.tracks, new.tracks):
            assert list(old_track) == list(new_track)

    def test_every_stage_round_trips_through_text(self):
        for stage, module in compile_piece(full_song()).stages.items():
            text = print_ir(module, locations=True)
            assert print_ir(parse_ir(text), locations=True) == text, stage


NUMERALS = [
    ("I", "major"),
    ("ii", "minor"),
    ("iii", "minor"),
    ("IV", "major"),
    ("V", "major"),
    ("vi", "minor"),
]
EXTENSIONS = [(), ("7",), ("maj7",), ("9",), ("sus4",), ("add9",), ("6",)]
PATTERNS = [
    ("root_quarters", {}),
    ("root_eighths", {}),
    ("root_fifths", {}),
    ("block_chords", {"rate": Fraction(1, 2)}),
    ("arp", {"direction": "up", "rate": Fraction(1, 2)}),
    ("arp", {"direction": "updown", "rate": Fraction(1, 3)}),
    ("rock_beat", {}),
    ("four_on_floor", {}),
    ("backbeat", {}),
    ("shuffle", {}),
]

chords = st.builds(
    lambda n, e, inv: Chord(numeral=n[0], quality=n[1], extensions=e, inversion=inv),
    st.sampled_from(NUMERALS),
    st.sampled_from(EXTENSIONS),
    st.integers(0, 2),
)
harmonies = st.lists(
    st.builds(
        ChordChange,
        chord=chords,
        duration=st.sampled_from([Fraction(1), Fraction(2), Fraction(1, 2)]),
    ),
    min_size=1,
    max_size=5,
).map(lambda changes: Harmony(changes=changes, duration_unit="bars"))
literal_notes = st.lists(
    st.builds(
        Note,
        pitch=st.integers(36, 96),
        duration=st.sampled_from([Fraction(1), Fraction(1, 2), Fraction(1, 3)]),
        velocity=st.one_of(st.none(), st.integers(1, 127)),
        offset=st.integers(0, 15).map(Fraction),
    ),
    max_size=12,
).map(lambda notes: Notes(notes=notes))
pattern_content = st.sampled_from(PATTERNS).map(
    lambda p: Pattern(pattern_type=p[0], params=dict(p[1]))
)


@st.composite
def tracks(draw, name: str) -> Track:
    return Track(
        name=name,
        role={"t1": "melody", "t2": "bass", "t3": "rhythm"}[name],
        content=draw(st.one_of(pattern_content, literal_notes)),
        octave_shift=draw(st.integers(-2, 2)),
        velocity=draw(st.integers(40, 127)),
        muted=draw(st.booleans()),
    )


@st.composite
def pieces(draw) -> Piece:
    names = draw(st.lists(st.sampled_from(["a", "b", "c"]), min_size=1, max_size=3, unique=True))
    sections = []
    for name in names:
        track_names = draw(st.lists(st.sampled_from(["t1", "t2", "t3"]), max_size=3, unique=True))
        sections.append(
            Section(
                name=name,
                bars=draw(st.integers(1, 4)),
                key=draw(
                    st.one_of(st.none(), st.sampled_from([Key("Eb", "major"), Key("A", "minor")]))
                ),
                time_signature=draw(
                    st.one_of(
                        st.none(), st.sampled_from([TimeSignature(3, 4), TimeSignature(7, 8)])
                    )
                ),
                harmony=draw(harmonies),
                tracks=[draw(tracks(n)) for n in track_names],
            )
        )
    form = draw(st.one_of(st.none(), st.lists(st.sampled_from(names), min_size=1, max_size=5)))
    return Piece(
        tempo=draw(st.sampled_from([90.0, 120.0, 150.5])),
        key=draw(st.sampled_from([Key("C", "major"), Key("F#", "minor"), Key("D", "dorian")])),
        time_signature=draw(st.sampled_from([TimeSignature(4, 4), TimeSignature(6, 8)])),
        sections=sections,
        form=form,
        title="generated",
    )


class TestGeneratedPieces:
    @settings(max_examples=150, deadline=None)
    @given(pieces())
    def test_generated_piece_matches_note_for_note(self, ir):
        assert_same_notes(ir)

    @settings(max_examples=40, deadline=None)
    @given(pieces())
    def test_generated_piece_round_trips(self, ir):
        for module in compile_piece(ir).stages.values():
            text = print_ir(module, locations=True)
            assert print_ir(parse_ir(text), locations=True) == text


class TestLocations:
    def test_repeated_section_keeps_its_note_names(self):
        module = compile_piece(full_song()).daw
        project = next(iter(module.body.block.ops))
        from pypulang.compiler.locs import loc_key

        keys = [loc_key(n.location) for t in project.tracks() for c in t.clips() for n in c.notes()]
        assert len(keys) == len(set(keys))
        assert "verse#1/bass/1+0/v0" in keys
        assert "verse#2/bass/1+0/v0" in keys
        assert not any("~" in k and "/drums/" not in k for k in keys)


def test_triplets_are_exact_at_960_ppq():
    with piece(tempo=120, key="C major") as p:
        s = p.section("a", bars=1)
        s.harmony(I)
        s.track("t", role=Role.HARMONY).pattern(arp("up"), rate=Fraction(1, 3))
    assert compile_piece(p.to_ir()).warnings == []
