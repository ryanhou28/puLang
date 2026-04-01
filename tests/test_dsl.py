"""
Tests for the pyPuLang DSL module.
"""

import pytest
from fractions import Fraction

from pypulang import (
    # Main entry point
    piece,
    # Role enum
    Role,
    # Roman numerals
    I, II, III, IV, V, VI, VII,
    i, ii, iii, iv, v, vi, vii,
    V7, Imaj7, IVmaj7, ii7,
    # Pattern singletons
    root_quarters,
    root_eighths,
    root_fifths,
    block_chords,
    arp,
    # Builder classes
    PieceBuilder,
    SectionBuilder,
    TrackBuilder,
    PatternBuilder,
    RomanNumeral,
    # IR types for verification
    Chord,
    Harmony,
    Pattern,
    Key,
    TimeSignature,
)


# -----------------------------------------------------------------------------
# Role Enum Tests
# -----------------------------------------------------------------------------


class TestRole:
    def test_role_values(self):
        """Role enum has correct string values."""
        assert Role.MELODY.value == "melody"
        assert Role.BASS.value == "bass"
        assert Role.HARMONY.value == "harmony"
        assert Role.RHYTHM.value == "rhythm"

    def test_role_members(self):
        """All expected roles exist."""
        assert len(Role) == 4
        roles = {Role.MELODY, Role.BASS, Role.HARMONY, Role.RHYTHM}
        assert len(roles) == 4


# -----------------------------------------------------------------------------
# Roman Numeral Tests
# -----------------------------------------------------------------------------


class TestRomanNumerals:
    def test_basic_major_numerals(self):
        """Major numerals exist and convert correctly."""
        chord = I.to_chord()
        assert chord.numeral == "I"
        assert chord.quality == "major"

        chord = IV.to_chord()
        assert chord.numeral == "IV"
        assert chord.quality == "major"

        chord = V.to_chord()
        assert chord.numeral == "V"
        assert chord.quality == "major"

    def test_basic_minor_numerals(self):
        """Minor numerals exist and convert correctly."""
        chord = ii.to_chord()
        assert chord.numeral == "ii"
        assert chord.quality == "minor"

        chord = vi.to_chord()
        assert chord.numeral == "vi"
        assert chord.quality == "minor"

    def test_quality_modifiers(self):
        """Quality modifiers work correctly."""
        # Diminished
        chord = vii.dim().to_chord()
        assert chord.quality == "diminished"

        # Augmented
        chord = III.aug().to_chord()
        assert chord.quality == "augmented"

    def test_extension_modifiers(self):
        """Extension modifiers work correctly."""
        # Dominant 7th
        chord = V.add7().to_chord()
        assert "7" in chord.extensions

        # Major 7th
        chord = I.maj7().to_chord()
        assert "maj7" in chord.extensions

        # Suspensions
        chord = IV.sus4().to_chord()
        assert "sus4" in chord.extensions

        chord = II.sus2().to_chord()
        assert "sus2" in chord.extensions

        # Add9
        chord = I.add9().to_chord()
        assert "add9" in chord.extensions

    def test_inversion_modifier(self):
        """Inversion modifier works correctly."""
        chord = I.inv(1).to_chord()
        assert chord.inversion == 1

        chord = V7.inv(2).to_chord()
        assert chord.inversion == 2

    def test_invalid_inversion(self):
        """Invalid inversion raises error."""
        with pytest.raises(ValueError):
            I.inv(5)

        with pytest.raises(ValueError):
            I.inv(-1)

    def test_altered_root_modifiers(self):
        """Flat and sharp root modifiers work."""
        # bVII
        chord = VII.flat().to_chord()
        assert chord.altered_root == -1

        # #IV
        chord = IV.sharp().to_chord()
        assert chord.altered_root == 1

    def test_secondary_dominant(self):
        """Secondary dominant syntax works."""
        # V/V
        chord = V.of(V).to_chord()
        assert chord.secondary == "V"

        # V/vi
        chord = V.of(vi).to_chord()
        assert chord.secondary == "vi"

        # Also works with string
        chord = V.of("IV").to_chord()
        assert chord.secondary == "IV"

    def test_method_chaining(self):
        """Multiple modifiers can be chained."""
        chord = V.add7().inv(1).to_chord()
        assert "7" in chord.extensions
        assert chord.inversion == 1

    def test_predefined_seventh_chords(self):
        """Predefined 7th chord constants work."""
        chord = V7.to_chord()
        assert chord.numeral == "V"
        assert "7" in chord.extensions

        chord = Imaj7.to_chord()
        assert "maj7" in chord.extensions

        chord = ii7.to_chord()
        assert chord.numeral == "ii"
        assert "7" in chord.extensions

    def test_repr(self):
        """String representation is reasonable."""
        assert "V" in repr(V)
        assert "7" in repr(V7)
        assert "b" in repr(VII.flat())
        assert "°" in repr(vii.dim())


# -----------------------------------------------------------------------------
# Pattern Singleton Tests
# -----------------------------------------------------------------------------


class TestPatternSingletons:
    def test_basic_patterns_exist(self):
        """All basic patterns exist."""
        assert root_quarters is not None
        assert root_eighths is not None
        assert root_fifths is not None
        assert block_chords is not None
        assert arp is not None

    def test_pattern_to_ir(self):
        """Patterns convert to IR correctly."""
        pattern = root_quarters.to_pattern()
        assert pattern.pattern_type == "root_quarters"

        pattern = arp.to_pattern()
        assert pattern.pattern_type == "arp"

    def test_pattern_call_with_args(self):
        """Patterns can be called with arguments."""
        pattern = arp("down").to_pattern()
        assert pattern.params.get("direction") == "down"

    def test_pattern_call_with_kwargs(self):
        """Patterns can be called with keyword arguments."""
        pattern = arp(direction="updown").to_pattern()
        assert pattern.params.get("direction") == "updown"

    def test_pattern_builder_methods(self):
        """Builder methods work on patterns."""
        pattern = arp.up().to_pattern()
        assert pattern.params.get("direction") == "up"

        pattern = arp.down().to_pattern()
        assert pattern.params.get("direction") == "down"

        pattern = arp.updown().to_pattern()
        assert pattern.params.get("direction") == "updown"

    def test_pattern_rate(self):
        """Rate parameter works."""
        pattern = block_chords.rate(0.5).to_pattern()
        assert pattern.params.get("rate") == 0.5

        pattern = arp.rate(Fraction(1, 16)).to_pattern()
        assert pattern.params.get("rate") == 1/16

    def test_pattern_chaining(self):
        """Multiple builder methods can be chained."""
        pattern = arp.up().rate(1/16).octaves(2).to_pattern()
        assert pattern.params.get("direction") == "up"
        assert pattern.params.get("rate") == 1/16
        assert pattern.params.get("octaves") == 2


# -----------------------------------------------------------------------------
# Piece Builder Tests
# -----------------------------------------------------------------------------


class TestPieceBuilder:
    def test_piece_creation(self):
        """piece() creates a PieceBuilder."""
        p = piece()
        assert isinstance(p, PieceBuilder)

    def test_piece_with_params(self):
        """piece() accepts parameters."""
        p = piece(tempo=100, key="G major", time_sig="3/4", title="Test")
        ir = p.to_ir()
        assert ir.tempo == 100
        assert ir.key.root == "G"
        assert ir.key.mode == "major"
        assert ir.time_signature.numerator == 3
        assert ir.time_signature.denominator == 4
        assert ir.title == "Test"

    def test_piece_context_manager(self):
        """piece() works as context manager."""
        with piece() as p:
            assert isinstance(p, PieceBuilder)
        # Should still be accessible after context
        ir = p.to_ir()
        assert ir is not None

    def test_piece_default_values(self):
        """piece() has sensible defaults."""
        p = piece()
        ir = p.to_ir()
        assert ir.tempo == 120.0
        assert ir.key.root == "C"
        assert ir.key.mode == "major"
        assert ir.time_signature.numerator == 4
        assert ir.time_signature.denominator == 4


# -----------------------------------------------------------------------------
# Section Builder Tests
# -----------------------------------------------------------------------------


class TestSectionBuilder:
    def test_section_creation(self):
        """Section can be created from piece."""
        with piece() as p:
            verse = p.section("verse", bars=8)
            assert isinstance(verse, SectionBuilder)
            assert verse.name == "verse"

    def test_section_to_ir(self):
        """Section converts to IR correctly."""
        with piece() as p:
            verse = p.section("verse", bars=8)
        ir = p.to_ir()
        assert len(ir.sections) == 1
        assert ir.sections[0].name == "verse"
        assert ir.sections[0].bars == 8

    def test_section_key_override(self):
        """Section can override key."""
        with piece(key="C major") as p:
            bridge = p.section("bridge", bars=4, key="G major")
        ir = p.to_ir()
        assert ir.sections[0].key is not None
        assert ir.sections[0].key.root == "G"

    def test_section_name_settable(self):
        """Section name can be changed."""
        with piece() as p:
            section = p.section("verse", bars=8)
            section.name = "chorus"
        ir = p.to_ir()
        assert ir.sections[0].name == "chorus"


# -----------------------------------------------------------------------------
# Harmony Tests
# -----------------------------------------------------------------------------


class TestHarmony:
    def test_basic_harmony(self):
        """Basic harmony with equal durations."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
        ir = p.to_ir()
        harmony = ir.sections[0].harmony
        assert len(harmony.changes) == 4
        # Each chord should be 1 bar
        for change in harmony.changes:
            assert change.duration == Fraction(1)

    def test_harmony_with_durations(self):
        """Harmony with explicit durations."""
        with piece() as p:
            verse = p.section("verse", bars=8)
            verse.harmony((I, 2), (IV, 2), (vi, 2), (V, 2))
        ir = p.to_ir()
        harmony = ir.sections[0].harmony
        assert len(harmony.changes) == 4
        for change in harmony.changes:
            assert change.duration == Fraction(2)

    def test_harmony_mixed_durations(self):
        """Harmony with mixed explicit and implicit durations."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.harmony((I, 2), IV, V)
        ir = p.to_ir()
        harmony = ir.sections[0].harmony
        assert harmony.changes[0].duration == Fraction(2)
        assert harmony.changes[1].duration == Fraction(1)  # default
        assert harmony.changes[2].duration == Fraction(1)  # default

    def test_progression_alias(self):
        """progression() is alias for harmony()."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.progression(I, IV, vi, V)
        ir = p.to_ir()
        assert len(ir.sections[0].harmony.changes) == 4

    def test_harmony_returns_section(self):
        """harmony() returns the section for chaining."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            result = verse.harmony(I, IV)
            assert result is verse


# -----------------------------------------------------------------------------
# Track Builder Tests
# -----------------------------------------------------------------------------


class TestTrackBuilder:
    def test_track_creation(self):
        """Track can be created from section."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            bass = verse.track("bass", role=Role.BASS)
            assert isinstance(bass, TrackBuilder)

    def test_track_to_ir(self):
        """Track converts to IR correctly."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.track("bass", role=Role.BASS, instrument="acoustic_bass")
        ir = p.to_ir()
        track = ir.sections[0].tracks[0]
        assert track.name == "bass"
        assert track.role == "bass"
        assert track.instrument == "acoustic_bass"

    def test_track_pattern(self):
        """Track accepts patterns."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass").pattern(root_quarters)
        ir = p.to_ir()
        track = ir.sections[0].tracks[0]
        assert track.content is not None
        assert track.content.pattern_type == "root_quarters"

    def test_track_pattern_with_params(self):
        """Track pattern can have parameters."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("keys").pattern(arp("up"), rate=1/16)
        ir = p.to_ir()
        track = ir.sections[0].tracks[0]
        assert track.content.params.get("direction") == "up"
        assert track.content.params.get("rate") == 1/16

    def test_track_octave(self):
        """Track octave shift works."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.track("bass").pattern(root_quarters).octave(-2)
        ir = p.to_ir()
        track = ir.sections[0].tracks[0]
        assert track.octave_shift == -2

    def test_track_velocity(self):
        """Track velocity works."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.track("bass").velocity(80)
        ir = p.to_ir()
        track = ir.sections[0].tracks[0]
        assert track.velocity == 80

    def test_track_velocity_validation(self):
        """Track velocity validates range."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            with pytest.raises(ValueError):
                verse.track("bass").velocity(200)

    def test_track_mute(self):
        """Track mute works."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.track("bass").mute()
        ir = p.to_ir()
        track = ir.sections[0].tracks[0]
        assert track.muted is True

    def test_track_chaining(self):
        """Track methods can be chained."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1).velocity(90)
        ir = p.to_ir()
        track = ir.sections[0].tracks[0]
        assert track.role == "bass"
        assert track.content.pattern_type == "root_quarters"
        assert track.octave_shift == -1
        assert track.velocity == 90


# -----------------------------------------------------------------------------
# Form Tests
# -----------------------------------------------------------------------------


class TestForm:
    def test_form_with_sections(self):
        """Form can be set with section objects."""
        with piece() as p:
            intro = p.section("intro", bars=4)
            verse = p.section("verse", bars=8)
            chorus = p.section("chorus", bars=8)
            p.form([intro, verse, chorus, verse, chorus])
        ir = p.to_ir()
        assert ir.form == ["intro", "verse", "chorus", "verse", "chorus"]

    def test_form_with_strings(self):
        """Form can be set with string names."""
        with piece() as p:
            p.section("verse", bars=8)
            p.section("chorus", bars=8)
            p.form(["verse", "chorus", "verse", "chorus"])
        ir = p.to_ir()
        assert ir.form == ["verse", "chorus", "verse", "chorus"]


# -----------------------------------------------------------------------------
# to_ir Tests
# -----------------------------------------------------------------------------


class TestToIR:
    def test_complete_piece_to_ir(self):
        """Complete piece converts to valid IR."""
        with piece(tempo=100, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        ir = p.to_ir()

        # Check piece level
        assert ir.tempo == 100
        assert ir.key.root == "C"
        assert ir.key.mode == "major"

        # Check section
        assert len(ir.sections) == 1
        section = ir.sections[0]
        assert section.name == "verse"
        assert section.bars == 4

        # Check harmony
        assert len(section.harmony.changes) == 4
        assert section.harmony.changes[0].chord.numeral == "I"
        assert section.harmony.changes[1].chord.numeral == "IV"
        assert section.harmony.changes[2].chord.numeral == "vi"
        assert section.harmony.changes[3].chord.numeral == "V"

        # Check track
        assert len(section.tracks) == 1
        track = section.tracks[0]
        assert track.name == "bass"
        assert track.role == "bass"
        assert track.octave_shift == -1
        assert track.content.pattern_type == "root_quarters"


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------


class TestIntegration:
    def test_roadmap_example(self):
        """The roadmap example from docs works."""
        with piece(tempo=100, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        # Should produce valid IR
        ir = p.to_ir()
        assert ir is not None
        assert len(ir.sections) == 1
        assert len(ir.sections[0].tracks) == 1

    def test_multiple_tracks(self):
        """Multiple tracks per section work."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
            verse.track("keys", role=Role.HARMONY).pattern(block_chords)

        ir = p.to_ir()
        assert len(ir.sections[0].tracks) == 2

    def test_multiple_sections(self):
        """Multiple sections work."""
        with piece() as p:
            p.section("verse", bars=8).harmony(I, IV, vi, V)
            p.section("chorus", bars=8).harmony(IV, V, I, vi)

        ir = p.to_ir()
        assert len(ir.sections) == 2
        assert ir.sections[0].name == "verse"
        assert ir.sections[1].name == "chorus"

    def test_complex_harmony(self):
        """Complex harmony with modifiers works."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.harmony(
                I,
                V.of(V),  # Secondary dominant
                V7,
                I.inv(1)
            )

        ir = p.to_ir()
        harmony = ir.sections[0].harmony
        assert harmony.changes[1].chord.secondary == "V"
        assert "7" in harmony.changes[2].chord.extensions
        assert harmony.changes[3].chord.inversion == 1
