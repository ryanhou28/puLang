"""Tests for pattern generators."""

from fractions import Fraction

import pytest

from pypulang.ir.intent import Chord, Key
from pypulang.patterns import (
    PATTERN_REGISTRY,
    arp,
    block_chords,
    generate_pattern,
    get_pattern,
    root_eighths,
    root_fifths,
    root_quarters,
)
from pypulang.resolution import resolve_chord


class TestPatternRegistry:
    """Tests for pattern registration and lookup."""

    def test_root_quarters_registered(self):
        assert "root_quarters" in PATTERN_REGISTRY

    def test_root_eighths_registered(self):
        assert "root_eighths" in PATTERN_REGISTRY

    def test_root_fifths_registered(self):
        assert "root_fifths" in PATTERN_REGISTRY

    def test_block_chords_registered(self):
        assert "block_chords" in PATTERN_REGISTRY

    def test_arp_registered(self):
        assert "arp" in PATTERN_REGISTRY

    def test_get_pattern_success(self):
        pattern = get_pattern("root_quarters")
        assert pattern is root_quarters

    def test_get_pattern_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown pattern"):
            get_pattern("nonexistent_pattern")


class TestRootQuarters:
    """Tests for the root_quarters pattern."""

    def test_generates_quarter_notes(self):
        """Should generate one note per beat."""
        chord_pitches = [60, 64, 67]  # C major triad
        duration = Fraction(4)  # 4 beats
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = root_quarters(chord_pitches, duration, offset, track_params, pattern_params)

        assert len(events) == 4
        for i, (pitch, start, dur, vel) in enumerate(events):
            assert pitch == 60  # Root note
            assert start == Fraction(i)
            assert dur == Fraction(1)
            assert vel == 100

    def test_applies_octave_shift(self):
        """Octave shift should transpose the root."""
        chord_pitches = [60, 64, 67]
        duration = Fraction(2)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": -1}  # Down one octave
        pattern_params = {}

        events = root_quarters(chord_pitches, duration, offset, track_params, pattern_params)

        # Root should be shifted down by 12 semitones
        assert events[0][0] == 48  # 60 - 12

    def test_respects_velocity(self):
        """Should use track velocity."""
        chord_pitches = [60, 64, 67]
        duration = Fraction(2)
        offset = Fraction(0)
        track_params = {"velocity": 80, "octave_shift": 0}
        pattern_params = {}

        events = root_quarters(chord_pitches, duration, offset, track_params, pattern_params)

        assert all(event[3] == 80 for event in events)

    def test_handles_offset(self):
        """Should respect the offset parameter."""
        chord_pitches = [60, 64, 67]
        duration = Fraction(2)
        offset = Fraction(8)  # Start at beat 8
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = root_quarters(chord_pitches, duration, offset, track_params, pattern_params)

        assert events[0][1] == Fraction(8)  # First note at beat 8
        assert events[1][1] == Fraction(9)  # Second note at beat 9

    def test_fractional_duration(self):
        """Should handle non-integer durations."""
        chord_pitches = [60, 64, 67]
        duration = Fraction(3, 2)  # 1.5 beats
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = root_quarters(chord_pitches, duration, offset, track_params, pattern_params)

        assert len(events) == 2
        # First note: full beat
        assert events[0][2] == Fraction(1)
        # Second note: half beat (truncated)
        assert events[1][2] == Fraction(1, 2)


class TestRootEighths:
    """Tests for the root_eighths pattern."""

    def test_generates_eighth_notes(self):
        """Should generate two notes per beat."""
        chord_pitches = [60, 64, 67]
        duration = Fraction(2)  # 2 beats
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = root_eighths(chord_pitches, duration, offset, track_params, pattern_params)

        assert len(events) == 4  # 2 beats * 2 eighths/beat
        for i, (pitch, start, dur, _vel) in enumerate(events):
            assert pitch == 60
            assert start == Fraction(i, 2)
            assert dur == Fraction(1, 2)


class TestRootFifths:
    """Tests for the root_fifths pattern."""

    def test_alternates_root_and_fifth(self):
        """Should alternate between root and fifth."""
        chord_pitches = [60, 64, 67]  # C major: C, E, G
        duration = Fraction(4)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = root_fifths(chord_pitches, duration, offset, track_params, pattern_params)

        assert len(events) == 4
        # Beat 1: root (60)
        assert events[0][0] == 60
        # Beat 2: fifth (67)
        assert events[1][0] == 67
        # Beat 3: root (60)
        assert events[2][0] == 60
        # Beat 4: fifth (67)
        assert events[3][0] == 67


class TestBlockChords:
    """Tests for the block_chords pattern."""

    def test_plays_all_chord_tones(self):
        """Should play all chord tones simultaneously."""
        chord_pitches = [60, 64, 67]  # C major
        duration = Fraction(2)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {"rate": 1}  # Quarter notes

        events = block_chords(chord_pitches, duration, offset, track_params, pattern_params)

        # 2 beats * 3 notes = 6 events
        assert len(events) == 6

        # First chord (beat 0)
        beat_0_events = [e for e in events if e[1] == Fraction(0)]
        assert len(beat_0_events) == 3
        assert sorted([e[0] for e in beat_0_events]) == [60, 64, 67]

    def test_respects_rate_param(self):
        """Should use the rate parameter for chord hits."""
        chord_pitches = [60, 64, 67]
        duration = Fraction(2)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {"rate": Fraction(1, 2)}  # Eighth notes

        events = block_chords(chord_pitches, duration, offset, track_params, pattern_params)

        # 2 beats / 0.5 = 4 hits * 3 notes = 12 events
        assert len(events) == 12


class TestArp:
    """Tests for the arp pattern."""

    def test_arp_up(self):
        """Should arpeggiate upward."""
        chord_pitches = [60, 64, 67]  # C, E, G
        duration = Fraction(2)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {"direction": "up", "rate": Fraction(1, 2)}

        events = arp(chord_pitches, duration, offset, track_params, pattern_params)

        # 2 beats / 0.5 = 4 notes
        assert len(events) == 4
        # Sequence: C, E, G, C (wraps)
        assert events[0][0] == 60  # C
        assert events[1][0] == 64  # E
        assert events[2][0] == 67  # G
        assert events[3][0] == 60  # C (wrapped)

    def test_arp_down(self):
        """Should arpeggiate downward."""
        chord_pitches = [60, 64, 67]
        duration = Fraction(3, 2)  # 1.5 beats
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {"direction": "down", "rate": Fraction(1, 2)}

        events = arp(chord_pitches, duration, offset, track_params, pattern_params)

        assert len(events) == 3
        # Sequence: G, E, C
        assert events[0][0] == 67  # G
        assert events[1][0] == 64  # E
        assert events[2][0] == 60  # C

    def test_arp_updown(self):
        """Should arpeggiate up then down."""
        chord_pitches = [60, 64, 67]
        duration = Fraction(5, 2)  # 2.5 beats for 5 eighth notes
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {"direction": "updown", "rate": Fraction(1, 2)}

        events = arp(chord_pitches, duration, offset, track_params, pattern_params)

        # Sequence: C, E, G, E, C (wrap...)
        assert len(events) == 5
        assert events[0][0] == 60  # C
        assert events[1][0] == 64  # E
        assert events[2][0] == 67  # G
        assert events[3][0] == 64  # E
        assert events[4][0] == 60  # C


class TestGeneratePattern:
    """Integration tests for generate_pattern function."""

    def test_generate_pattern_delegates(self):
        """Should correctly delegate to registered pattern."""
        chord_pitches = [60, 64, 67]
        duration = Fraction(2)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = generate_pattern(
            "root_quarters",
            chord_pitches,
            duration,
            offset,
            track_params,
            pattern_params,
        )

        assert len(events) == 2
        assert all(e[0] == 60 for e in events)


class TestPatternWithChordResolution:
    """Integration tests combining chord resolution and patterns."""

    def test_i_iv_vi_v_bass_line(self):
        """Test generating a bass line for I-IV-vi-V progression."""
        key = Key("C", "major")
        track_params = {"velocity": 100, "octave_shift": -2}  # Bass register
        pattern_params = {}

        progression = [
            (Chord("I", "major"), Fraction(4)),  # 4 beats
            (Chord("IV", "major"), Fraction(4)),  # 4 beats
            (Chord("vi", "minor"), Fraction(4)),  # 4 beats
            (Chord("V", "major"), Fraction(4)),  # 4 beats
        ]

        all_events = []
        current_offset = Fraction(0)

        for chord, duration in progression:
            chord_pitches = resolve_chord(chord, key, octave=4)
            events = generate_pattern(
                "root_quarters",
                chord_pitches,
                duration,
                current_offset,
                track_params,
                pattern_params,
            )
            all_events.extend(events)
            current_offset += duration

        # Should have 16 notes total (4 beats per chord, 4 chords)
        assert len(all_events) == 16

        # Check root notes (at octave 2 due to -2 shift)
        # I = C (60 - 24 = 36)
        assert all_events[0][0] == 36  # C2
        # IV = F (65 - 24 = 41)
        assert all_events[4][0] == 41  # F2
        # vi = A (69 - 24 = 45)
        assert all_events[8][0] == 45  # A2
        # V = G (67 - 24 = 43)
        assert all_events[12][0] == 43  # G2

    def test_arpeggiated_accompaniment(self):
        """Test generating arpeggiated accompaniment for a chord."""
        key = Key("G", "major")
        chord = Chord("I", "major")  # G major
        chord_pitches = resolve_chord(chord, key, octave=4)

        track_params = {"velocity": 80, "octave_shift": 0}
        pattern_params = {"direction": "up", "rate": Fraction(1, 4)}  # 16th notes

        events = generate_pattern(
            "arp",
            chord_pitches,
            Fraction(4),  # 4 beats
            Fraction(0),
            track_params,
            pattern_params,
        )

        # 4 beats / 0.25 = 16 sixteenth notes
        assert len(events) == 16

        # Check pattern cycles through G, B, D
        assert events[0][0] == 67  # G4
        assert events[1][0] == 71  # B4
        assert events[2][0] == 74  # D5
        assert events[3][0] == 67  # G4 (wraps)
