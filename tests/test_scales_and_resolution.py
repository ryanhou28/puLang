"""Tests for music theory functions."""

import pytest

from pypulang.ir.intent import Chord, Key

# Optional hypothesis import for property-based tests
try:
    from hypothesis import given
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

    # Create dummy decorators
    def given(*args, **kwargs):
        def decorator(func):
            return pytest.mark.skip(reason="hypothesis not installed")(func)

        return decorator

    class st:
        @staticmethod
        def sampled_from(items):
            return None

        @staticmethod
        def integers(**kwargs):
            return None


from pypulang.resolution import (
    get_bass_note,
    get_chord_root_pitch,
    resolve_chord,
)
from pypulang.scales import (
    get_key_root_pitch,
    get_scale_pitches,
    pitch_class_to_semitone,
)


class TestPitchClassToSemitone:
    """Tests for pitch class to semitone conversion."""

    def test_natural_notes(self):
        assert pitch_class_to_semitone("C") == 0
        assert pitch_class_to_semitone("D") == 2
        assert pitch_class_to_semitone("E") == 4
        assert pitch_class_to_semitone("F") == 5
        assert pitch_class_to_semitone("G") == 7
        assert pitch_class_to_semitone("A") == 9
        assert pitch_class_to_semitone("B") == 11

    def test_sharps(self):
        assert pitch_class_to_semitone("C#") == 1
        assert pitch_class_to_semitone("D#") == 3
        assert pitch_class_to_semitone("F#") == 6
        assert pitch_class_to_semitone("G#") == 8
        assert pitch_class_to_semitone("A#") == 10

    def test_flats(self):
        assert pitch_class_to_semitone("Db") == 1
        assert pitch_class_to_semitone("Eb") == 3
        assert pitch_class_to_semitone("Gb") == 6
        assert pitch_class_to_semitone("Ab") == 8
        assert pitch_class_to_semitone("Bb") == 10

    def test_enharmonic_equivalence(self):
        assert pitch_class_to_semitone("C#") == pitch_class_to_semitone("Db")
        assert pitch_class_to_semitone("F#") == pitch_class_to_semitone("Gb")

    def test_wrap_around(self):
        # Cb is enharmonic to B
        assert pitch_class_to_semitone("Cb") == 11

    def test_invalid_note_raises(self):
        with pytest.raises(ValueError):
            pitch_class_to_semitone("H")

    def test_invalid_accidental_raises(self):
        with pytest.raises(ValueError):
            pitch_class_to_semitone("C##")


class TestGetScalePitches:
    """Tests for scale interval retrieval."""

    def test_major_scale(self):
        key = Key("C", "major")
        assert get_scale_pitches(key) == [0, 2, 4, 5, 7, 9, 11]

    def test_minor_scale(self):
        key = Key("A", "minor")
        assert get_scale_pitches(key) == [0, 2, 3, 5, 7, 8, 10]

    def test_dorian_scale(self):
        key = Key("D", "dorian")
        assert get_scale_pitches(key) == [0, 2, 3, 5, 7, 9, 10]

    def test_mixolydian_scale(self):
        key = Key("G", "mixolydian")
        assert get_scale_pitches(key) == [0, 2, 4, 5, 7, 9, 10]


class TestGetKeyRootPitch:
    """Tests for key root pitch calculation."""

    def test_c4_is_60(self):
        assert get_key_root_pitch(Key("C", "major"), octave=4) == 60

    def test_a4_is_69(self):
        assert get_key_root_pitch(Key("A", "major"), octave=4) == 69

    def test_g3_is_55(self):
        assert get_key_root_pitch(Key("G", "major"), octave=3) == 55

    def test_f_sharp_4(self):
        assert get_key_root_pitch(Key("F#", "major"), octave=4) == 66


class TestResolveChordMajorKey:
    """Tests for chord resolution in major keys."""

    def test_c_major_I(self):
        """I chord in C major = C major triad = C4, E4, G4"""
        chord = Chord("I", "major")
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [60, 64, 67]  # C4, E4, G4

    def test_c_major_ii(self):
        """ii chord in C major = D minor triad = D4, F4, A4"""
        chord = Chord("ii", "minor")
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [62, 65, 69]  # D4, F4, A4

    def test_c_major_iii(self):
        """iii chord in C major = E minor triad = E4, G4, B4"""
        chord = Chord("iii", "minor")
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [64, 67, 71]  # E4, G4, B4

    def test_c_major_IV(self):
        """IV chord in C major = F major triad = F4, A4, C5"""
        chord = Chord("IV", "major")
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [65, 69, 72]  # F4, A4, C5

    def test_c_major_V(self):
        """V chord in C major = G major triad = G4, B4, D5"""
        chord = Chord("V", "major")
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [67, 71, 74]  # G4, B4, D5

    def test_c_major_vi(self):
        """vi chord in C major = A minor triad = A4, C5, E5"""
        chord = Chord("vi", "minor")
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [69, 72, 76]  # A4, C5, E5

    def test_c_major_vii_dim(self):
        """vii° chord in C major = B diminished triad = B4, D5, F5"""
        chord = Chord("vii", "diminished")
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [71, 74, 77]  # B4, D5, F5


class TestResolveChordMinorKey:
    """Tests for chord resolution in minor keys."""

    def test_a_minor_i(self):
        """i chord in A minor = A minor triad = A4, C5, E5"""
        chord = Chord("i", "minor")
        key = Key("A", "minor")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [69, 72, 76]  # A4, C5, E5

    def test_a_minor_iv(self):
        """iv chord in A minor = D minor triad = D4, F4, A4"""
        # In A natural minor, scale is A B C D E F G
        # iv = D minor
        chord = Chord("iv", "minor")
        key = Key("A", "minor")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [62, 65, 69]  # D4, F4, A4

    def test_a_minor_V(self):
        """V chord in A minor = E major triad = E4, G#4, B4"""
        # Note: In natural minor, v is minor; using V major here
        chord = Chord("V", "major")
        key = Key("A", "minor")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [64, 68, 71]  # E4, G#4, B4


class TestResolveChordOtherKeys:
    """Tests for chord resolution in various other keys."""

    def test_g_major_I(self):
        """I chord in G major = G major triad = G4, B4, D5"""
        chord = Chord("I", "major")
        key = Key("G", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [67, 71, 74]  # G4, B4, D5

    def test_d_major_V7(self):
        """V7 chord in D major = A7 = A4, C#5, E5, G5"""
        chord = Chord("V", "major", extensions=("7",))
        key = Key("D", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [69, 73, 76, 79]  # A4, C#5, E5, G5

    def test_f_major_IV(self):
        """IV chord in F major = Bb major triad"""
        chord = Chord("IV", "major")
        key = Key("F", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [70, 74, 77]  # Bb4, D5, F5


class TestResolveChordExtensions:
    """Tests for chords with extensions."""

    def test_dominant_7th(self):
        """V7 in C major = G7 = G4, B4, D5, F5"""
        chord = Chord("V", "major", extensions=("7",))
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [67, 71, 74, 77]  # G4, B4, D5, F5

    def test_major_7th(self):
        """Imaj7 in C major = Cmaj7 = C4, E4, G4, B4"""
        chord = Chord("I", "major", extensions=("maj7",))
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [60, 64, 67, 71]  # C4, E4, G4, B4

    def test_sus4(self):
        """Isus4 in C major = Csus4 = C4, F4, G4"""
        chord = Chord("I", "major", extensions=("sus4",))
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [60, 65, 67]  # C4, F4, G4

    def test_sus2(self):
        """Isus2 in C major = Csus2 = C4, D4, G4"""
        chord = Chord("I", "major", extensions=("sus2",))
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [60, 62, 67]  # C4, D4, G4

    def test_add9(self):
        """Iadd9 in C major = Cadd9 = C4, E4, G4, D5"""
        chord = Chord("I", "major", extensions=("add9",))
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [60, 64, 67, 74]  # C4, E4, G4, D5


class TestResolveChordInversions:
    """Tests for chord inversions."""

    def test_root_position(self):
        """Root position: C, E, G"""
        chord = Chord("I", "major", inversion=0)
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert pitches == [60, 64, 67]
        assert pitches[0] == 60  # C is bass

    def test_first_inversion(self):
        """First inversion: E is bass, C and G above"""
        chord = Chord("I", "major", inversion=1)
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        # After inversion: C moves up an octave
        assert pitches == [64, 67, 72]  # E4, G4, C5
        assert pitches[0] == 64  # E is bass

    def test_second_inversion(self):
        """Second inversion: G is bass"""
        chord = Chord("I", "major", inversion=2)
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        # After inversion: C and E move up an octave
        assert pitches == [67, 72, 76]  # G4, C5, E5
        assert pitches[0] == 67  # G is bass


class TestResolveChordAugmentedDiminished:
    """Tests for augmented and diminished chords."""

    def test_diminished_triad(self):
        """Diminished triad: 1, b3, b5"""
        chord = Chord("vii", "diminished")
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        # B dim = B, D, F
        assert pitches == [71, 74, 77]  # B4, D5, F5

    def test_augmented_triad(self):
        """Augmented triad: 1, 3, #5"""
        chord = Chord("III", "augmented")
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        # E aug = E, G#, B#(C)
        assert pitches == [64, 68, 72]  # E4, G#4, C5


class TestGetChordRootPitch:
    """Tests for chord root pitch extraction."""

    def test_I_in_c_major(self):
        chord = Chord("I", "major")
        key = Key("C", "major")
        assert get_chord_root_pitch(chord, key, octave=4) == 60  # C4

    def test_V_in_c_major(self):
        chord = Chord("V", "major")
        key = Key("C", "major")
        assert get_chord_root_pitch(chord, key, octave=4) == 67  # G4

    def test_vi_in_c_major(self):
        chord = Chord("vi", "minor")
        key = Key("C", "major")
        assert get_chord_root_pitch(chord, key, octave=4) == 69  # A4

    def test_bass_octave(self):
        chord = Chord("I", "major")
        key = Key("C", "major")
        assert get_chord_root_pitch(chord, key, octave=2) == 36  # C2


class TestGetBassNote:
    """Tests for bass note extraction with inversions."""

    def test_root_position_bass(self):
        chord = Chord("I", "major", inversion=0)
        key = Key("C", "major")
        assert get_bass_note(chord, key, octave=2) == 36  # C2

    def test_first_inversion_bass(self):
        chord = Chord("I", "major", inversion=1)
        key = Key("C", "major")
        # First inversion: E in bass
        assert get_bass_note(chord, key, octave=2) == 40  # E2

    def test_second_inversion_bass(self):
        chord = Chord("I", "major", inversion=2)
        key = Key("C", "major")
        # Second inversion: G in bass
        assert get_bass_note(chord, key, octave=2) == 43  # G2


class TestChordResolutionProgression:
    """Test complete chord progressions."""

    def test_i_iv_vi_v_in_c_major(self):
        """Classic I-IV-vi-V progression in C major."""
        key = Key("C", "major")

        # I = C major
        I = resolve_chord(Chord("I", "major"), key, octave=4)
        assert I == [60, 64, 67]

        # IV = F major
        IV = resolve_chord(Chord("IV", "major"), key, octave=4)
        assert IV == [65, 69, 72]

        # vi = A minor
        vi = resolve_chord(Chord("vi", "minor"), key, octave=4)
        assert vi == [69, 72, 76]

        # V = G major
        V = resolve_chord(Chord("V", "major"), key, octave=4)
        assert V == [67, 71, 74]

    def test_i_iv_vi_v_in_g_major(self):
        """I-IV-vi-V progression in G major."""
        key = Key("G", "major")

        # I = G major (G4=67, B4=71, D5=74)
        I = resolve_chord(Chord("I", "major"), key, octave=4)
        assert I == [67, 71, 74]  # G, B, D

        # IV = C major (C4=60, E4=64, G4=67)
        IV = resolve_chord(Chord("IV", "major"), key, octave=4)
        assert IV == [60, 64, 67]  # C4, E4, G4

        # vi = E minor (E4=64, G4=67, B4=71)
        vi = resolve_chord(Chord("vi", "minor"), key, octave=4)
        assert vi == [64, 67, 71]  # E4, G4, B4

        # V = D major (D4=62, F#4=66, A4=69)
        V = resolve_chord(Chord("V", "major"), key, octave=4)
        assert V == [62, 66, 69]  # D4, F#4, A4


# Hypothesis-based property tests
class TestChordResolutionProperties:
    """Property-based tests for chord resolution."""

    @given(
        st.sampled_from(["C", "D", "E", "F", "G", "A", "B"]), st.sampled_from(["major", "minor"])
    )
    def test_triad_has_three_notes(self, root, mode):
        """All triads should have exactly 3 notes."""
        chord = Chord("I", "major")
        key = Key(root, mode)
        pitches = resolve_chord(chord, key, octave=4)
        assert len(pitches) == 3

    @given(
        st.sampled_from(["C", "D", "E", "F", "G", "A", "B"]), st.sampled_from(["major", "minor"])
    )
    def test_seventh_chord_has_four_notes(self, root, mode):
        """All 7th chords should have exactly 4 notes."""
        chord = Chord("V", "major", extensions=("7",))
        key = Key(root, mode)
        pitches = resolve_chord(chord, key, octave=4)
        assert len(pitches) == 4

    @given(
        st.sampled_from(["C", "D", "E", "F", "G", "A", "B"]),
        st.sampled_from(["major", "minor"]),
        st.integers(min_value=0, max_value=7),
    )
    def test_pitches_are_in_midi_range(self, root, mode, octave):
        """All pitches should be valid MIDI values."""
        chord = Chord("I", "major")
        key = Key(root, mode)
        pitches = resolve_chord(chord, key, octave=octave)
        for pitch in pitches:
            assert 0 <= pitch <= 127

    @given(st.sampled_from(["I", "II", "III", "IV", "V", "VI", "VII"]))
    def test_all_major_degrees_resolve(self, numeral):
        """All scale degrees should resolve without error."""
        chord = Chord(numeral, "major")
        key = Key("C", "major")
        pitches = resolve_chord(chord, key, octave=4)
        assert len(pitches) >= 3
