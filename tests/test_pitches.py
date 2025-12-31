"""
Tests for the pypulang pitches module - escape hatch for literal notes.
"""

import pytest
from fractions import Fraction

from pypulang.pitches import (
    # Core class
    Pitch,
    # Note specification functions
    note,
    rest,
    chord,
    NoteSpec,
    ChordSpec,
    REST,
    # Common pitches for testing
    C4, D4, E4, F4, G4, A4, B4,
    C5, D5, E5, G5,
    Cs4, Db4, Ds4, Eb4, Fs4, Gb4, Gs4, Ab4, As4, Bb4,
    C3, C2, C1, C0,
    C6, C7, C8,
)


# -----------------------------------------------------------------------------
# Pitch Class Tests
# -----------------------------------------------------------------------------


class TestPitch:
    def test_pitch_is_int_subclass(self):
        """Pitch is an int subclass."""
        assert isinstance(C4, int)
        assert isinstance(C4, Pitch)

    def test_pitch_values(self):
        """Standard pitches have correct MIDI values."""
        # Middle C is MIDI 60
        assert C4 == 60
        # Concert A is MIDI 69
        assert A4 == 69
        # D4 is 62
        assert D4 == 62
        # G4 is 67
        assert G4 == 67

    def test_pitch_octaves(self):
        """Pitches in different octaves differ by 12."""
        assert C5 - C4 == 12
        assert C4 - C3 == 12
        assert C3 - C2 == 12

    def test_sharps_and_flats(self):
        """Sharp and flat variants are correct."""
        # Cs4 and Db4 are the same pitch
        assert Cs4 == Db4 == 61
        # Fs4 and Gb4 are the same
        assert Fs4 == Gb4 == 66
        # Bb4 is B flat
        assert Bb4 == 70

    def test_pitch_addition(self):
        """Pitch + int returns Pitch."""
        result = C4 + 7
        assert isinstance(result, Pitch)
        assert result == 67  # G4

    def test_pitch_subtraction(self):
        """Pitch - int returns Pitch."""
        result = C4 - 12
        assert isinstance(result, Pitch)
        assert result == 48  # C3

    def test_pitch_reverse_addition(self):
        """int + Pitch returns Pitch."""
        result = 5 + C4
        assert isinstance(result, Pitch)
        assert result == 65  # F4

    def test_octave_up(self):
        """octave_up() returns pitch shifted up."""
        result = C4.octave_up()
        assert result == 72  # C5
        assert isinstance(result, Pitch)

    def test_octave_up_multiple(self):
        """octave_up(n) shifts by n octaves."""
        result = C4.octave_up(2)
        assert result == 84  # C6

    def test_octave_down(self):
        """octave_down() returns pitch shifted down."""
        result = C4.octave_down()
        assert result == 48  # C3
        assert isinstance(result, Pitch)

    def test_transpose(self):
        """transpose() shifts by semitones."""
        # Major third up
        result = C4.transpose(4)
        assert result == 64  # E4

        # Perfect fifth up
        result = C4.transpose(7)
        assert result == 67  # G4

    def test_midi_property(self):
        """midi property returns raw int."""
        assert C4.midi == 60

    def test_octave_property(self):
        """octave property returns correct octave."""
        assert C4.octave == 4
        assert C5.octave == 5
        assert C3.octave == 3

    def test_note_name_property(self):
        """note_name property returns note without octave."""
        assert C4.note_name == "C"
        assert Cs4.note_name == "C#"
        assert A4.note_name == "A"

    def test_pitch_str(self):
        """String representation includes note and octave."""
        assert str(C4) == "C4"
        assert str(A4) == "A4"

    def test_pitch_repr(self):
        """Repr shows Pitch constructor."""
        assert "60" in repr(C4)


# -----------------------------------------------------------------------------
# NoteSpec Tests
# -----------------------------------------------------------------------------


class TestNoteSpec:
    def test_note_basic(self):
        """note() creates NoteSpec with pitch and duration."""
        n = note(C4, Fraction(1, 4))
        assert isinstance(n, NoteSpec)
        assert n.pitch == 60
        assert n.duration == Fraction(1, 4)
        assert n.velocity is None

    def test_note_with_velocity(self):
        """note() accepts velocity parameter."""
        n = note(C4, Fraction(1, 4), velocity=100)
        assert n.velocity == 100

    def test_note_duration_conversion(self):
        """note() converts float/int durations to Fraction."""
        n = note(C4, 0.25)
        assert n.duration == Fraction(1, 4)

        n = note(C4, 1)
        assert n.duration == Fraction(1, 1)

    def test_note_accepts_pitch_object(self):
        """note() accepts Pitch constants."""
        n = note(C4, 1/4)
        assert n.pitch == 60

    def test_note_accepts_int(self):
        """note() accepts raw int for pitch."""
        n = note(60, 1/4)
        assert n.pitch == 60


# -----------------------------------------------------------------------------
# Rest Tests
# -----------------------------------------------------------------------------


class TestRest:
    def test_rest_basic(self):
        """rest() creates NoteSpec with pitch=-1."""
        r = rest(Fraction(1, 4))
        assert isinstance(r, NoteSpec)
        assert r.pitch == -1
        assert r.duration == Fraction(1, 4)

    def test_rest_duration_conversion(self):
        """rest() converts float durations."""
        r = rest(0.5)
        assert r.duration == Fraction(1, 2)

    def test_rest_constant(self):
        """REST constant equals -1."""
        assert REST == -1


# -----------------------------------------------------------------------------
# ChordSpec Tests
# -----------------------------------------------------------------------------


class TestChordSpec:
    def test_chord_basic(self):
        """chord() creates ChordSpec with multiple pitches."""
        c = chord([C4, E4, G4], Fraction(1, 2))
        assert isinstance(c, ChordSpec)
        assert c.pitches == [60, 64, 67]
        assert c.duration == Fraction(1, 2)
        assert c.velocity is None

    def test_chord_with_velocity(self):
        """chord() accepts velocity parameter."""
        c = chord([C4, E4, G4], Fraction(1, 2), velocity=80)
        assert c.velocity == 80

    def test_chord_duration_conversion(self):
        """chord() converts duration types."""
        c = chord([C4, E4], 0.25)
        assert c.duration == Fraction(1, 4)

    def test_chord_accepts_pitch_objects(self):
        """chord() accepts Pitch constants in list."""
        c = chord([C4, E4, G4], 1/2)
        assert c.pitches == [60, 64, 67]


# -----------------------------------------------------------------------------
# Pitch Constant Coverage Tests
# -----------------------------------------------------------------------------


class TestPitchConstants:
    def test_all_octaves_exist(self):
        """All octaves 0-8 have C defined."""
        assert C0 == 12
        assert C1 == 24
        assert C2 == 36
        assert C3 == 48
        assert C4 == 60
        assert C5 == 72
        assert C6 == 84
        assert C7 == 96
        assert C8 == 108

    def test_chromatic_scale_at_octave_4(self):
        """All 12 notes in octave 4 are correct."""
        expected = [60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71]
        actual = [C4, Cs4, D4, Ds4, E4, F4, Fs4, G4, Gs4, A4, As4, B4]
        assert actual == expected

    def test_enharmonic_equivalents(self):
        """Enharmonic equivalents have same value."""
        assert Cs4 == Db4
        assert Ds4 == Eb4
        assert Fs4 == Gb4
        assert Gs4 == Ab4
        assert As4 == Bb4


# -----------------------------------------------------------------------------
# Integration with DSL Tests
# -----------------------------------------------------------------------------


class TestDSLIntegration:
    def test_track_notes_with_tuples(self):
        """Track.notes() accepts tuple syntax."""
        from pypulang import piece, Role

        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.track("melody", role=Role.MELODY).notes([
                (C4, Fraction(1, 4)),
                (E4, Fraction(1, 4)),
                (G4, Fraction(1, 2)),
            ])

        ir = p.to_ir()
        track = ir.sections[0].tracks[0]
        notes = track.content.notes

        assert len(notes) == 3
        assert notes[0].pitch == 60
        assert notes[0].duration == Fraction(1, 4)
        assert notes[0].offset == Fraction(0)

        assert notes[1].pitch == 64
        assert notes[1].offset == Fraction(1, 4)

        assert notes[2].pitch == 67
        assert notes[2].duration == Fraction(1, 2)
        assert notes[2].offset == Fraction(1, 2)

    def test_track_notes_with_note_function(self):
        """Track.notes() accepts note() specifications."""
        from pypulang import piece, Role

        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.track("melody").notes([
                note(C4, 1/4),
                note(E4, 1/4, velocity=100),
            ])

        ir = p.to_ir()
        notes = ir.sections[0].tracks[0].content.notes

        assert notes[0].pitch == 60
        assert notes[0].velocity is None

        assert notes[1].pitch == 64
        assert notes[1].velocity == 100

    def test_track_notes_with_rests(self):
        """Track.notes() handles rests correctly."""
        from pypulang import piece

        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.track("melody").notes([
                (C4, 1/4),
                rest(1/4),
                (E4, 1/4),
            ])

        ir = p.to_ir()
        notes = ir.sections[0].tracks[0].content.notes

        assert len(notes) == 3
        # First note at offset 0
        assert notes[0].offset == Fraction(0)
        # Rest at offset 1/4
        assert notes[1].pitch == -1
        assert notes[1].offset == Fraction(1, 4)
        # Third note at offset 1/2
        assert notes[2].offset == Fraction(1, 2)

    def test_track_notes_with_chords(self):
        """Track.notes() handles chord() correctly."""
        from pypulang import piece

        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.track("keys").notes([
                chord([C4, E4, G4], 1/2),
                chord([D4, F4, A4], 1/2),
            ])

        ir = p.to_ir()
        notes = ir.sections[0].tracks[0].content.notes

        # First chord: 3 notes at offset 0
        assert len([n for n in notes if n.offset == Fraction(0)]) == 3
        # Second chord: 3 notes at offset 1/2
        assert len([n for n in notes if n.offset == Fraction(1, 2)]) == 3
        # Total 6 notes
        assert len(notes) == 6

    def test_track_notes_with_mixed_types(self):
        """Track.notes() handles mixed input types."""
        from pypulang import piece

        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.track("melody").notes([
                (C4, 1/4),  # tuple
                note(E4, 1/4, velocity=100),  # NoteSpec
                rest(1/4),  # rest
                chord([G4, B4, D5], 1/4),  # ChordSpec
            ])

        ir = p.to_ir()
        notes = ir.sections[0].tracks[0].content.notes

        # 1 + 1 + 1 + 3 = 6 notes total
        assert len(notes) == 6

    def test_track_notes_with_octave_shift(self):
        """Track octave shift applies to literal notes."""
        from pypulang import piece

        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.track("bass").notes([
                (C4, 1/2),
            ]).octave(-1)

        ir = p.to_ir()
        track = ir.sections[0].tracks[0]
        assert track.octave_shift == -1
        # Note pitch is stored as-is; octave shift applied in MIDI realization
        assert track.content.notes[0].pitch == 60


# -----------------------------------------------------------------------------
# MIDI Integration Tests
# -----------------------------------------------------------------------------


class TestMIDIIntegration:
    def test_literal_notes_to_midi(self):
        """Literal notes produce valid MIDI output."""
        from pypulang import piece

        with piece(tempo=120) as p:
            verse = p.section("verse", bars=2)
            verse.track("melody").notes([
                (C4, 1/4),
                (E4, 1/4),
                (G4, 1/4),
                rest(1/4),
                chord([C4, E4, G4], 1/2),
                rest(1/2),
            ])

        # Should produce valid MIDI without errors
        midi = p.to_midi()
        assert midi is not None
        # Conductor track + 1 content track
        assert len(midi.tracks) == 2

    def test_mixed_patterns_and_notes(self):
        """Section can have both pattern and literal note tracks."""
        from pypulang import piece, Role, root_quarters, I, IV, vi, V

        with piece(tempo=100, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)
            verse.track("melody", role=Role.MELODY).notes([
                (E5, 1/4), (D5, 1/4), (C5, 1/2),
                (D5, 1/4), (E5, 1/4), (E5, 1/2),
            ])

        midi = p.to_midi()
        assert midi is not None
        # Conductor + bass + melody
        assert len(midi.tracks) == 3
