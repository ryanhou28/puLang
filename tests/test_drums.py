"""
Tests for drum patterns and percussion (Phase 2.5).
"""

from fractions import Fraction

from pypulang import Role, piece
from pypulang.drums import (
    COWBELL,
    CRASH,
    HIHAT_CLOSED,
    HIHAT_OPEN,
    KICK,
    SNARE,
    TAMBOURINE,
)
from pypulang.midi import realize_to_midi
from pypulang.patterns import generate_pattern


class TestDrumConstants:
    """Test that drum constants are defined correctly."""

    def test_kick_drum_constant(self):
        """Kick drum should be MIDI note 36."""
        assert KICK.midi == 36

    def test_snare_drum_constant(self):
        """Snare drum should be MIDI note 38."""
        assert SNARE.midi == 38

    def test_hihat_constants(self):
        """Hi-hat constants should be defined."""
        assert HIHAT_CLOSED.midi == 42
        assert HIHAT_OPEN.midi == 46

    def test_cymbal_constants(self):
        """Cymbal constants should be defined."""
        assert CRASH.midi == 49

    def test_percussion_constants(self):
        """Percussion constants should be defined."""
        assert COWBELL.midi == 56
        assert TAMBOURINE.midi == 54


class TestDrumPatterns:
    """Test drum pattern generators."""

    def test_rock_beat_generates_notes(self):
        """Rock beat should generate kick, snare, and hi-hat notes."""
        # Rock beat ignores chord pitches
        chord_pitches = []
        duration = Fraction(4)  # 4 beats
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = generate_pattern(
            "rock_beat", chord_pitches, duration, offset, track_params, pattern_params
        )

        # Should have events (kick, snare, and hi-hats)
        assert len(events) > 0

        # Check that we have kicks, snares, and hi-hats
        pitches = {event[0] for event in events}
        assert KICK.midi in pitches  # Kick drum
        assert SNARE.midi in pitches  # Snare drum
        assert HIHAT_CLOSED.midi in pitches  # Hi-hat

    def test_rock_beat_kick_on_beats_1_and_3(self):
        """Rock beat should have kick on beats 1 and 3."""
        chord_pitches = []
        duration = Fraction(4)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = generate_pattern(
            "rock_beat", chord_pitches, duration, offset, track_params, pattern_params
        )

        # Find kick events
        kick_events = [e for e in events if e[0] == KICK.midi]

        # Should have kicks on beat 0 and 2 (0-indexed)
        kick_times = {e[1] for e in kick_events}
        assert Fraction(0) in kick_times  # Beat 1
        assert Fraction(2) in kick_times  # Beat 3

    def test_rock_beat_snare_on_beats_2_and_4(self):
        """Rock beat should have snare on beats 2 and 4."""
        chord_pitches = []
        duration = Fraction(4)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = generate_pattern(
            "rock_beat", chord_pitches, duration, offset, track_params, pattern_params
        )

        # Find snare events
        snare_events = [e for e in events if e[0] == SNARE.midi]

        # Should have snares on beat 1 and 3 (0-indexed)
        snare_times = {e[1] for e in snare_events}
        assert Fraction(1) in snare_times  # Beat 2
        assert Fraction(3) in snare_times  # Beat 4

    def test_rock_beat_hihat_parameter(self):
        """Rock beat should support hihat parameter (closed/open)."""
        chord_pitches = []
        duration = Fraction(4)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}

        # Test with closed hi-hat (default)
        events_closed = generate_pattern(
            "rock_beat",
            chord_pitches,
            duration,
            offset,
            track_params,
            {"hihat": "closed"},
        )
        assert any(e[0] == HIHAT_CLOSED.midi for e in events_closed)

        # Test with open hi-hat
        events_open = generate_pattern(
            "rock_beat",
            chord_pitches,
            duration,
            offset,
            track_params,
            {"hihat": "open"},
        )
        assert any(e[0] == HIHAT_OPEN.midi for e in events_open)

    def test_four_on_floor_kick_every_beat(self):
        """Four-on-the-floor should have kick on every beat."""
        chord_pitches = []
        duration = Fraction(4)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = generate_pattern(
            "four_on_floor",
            chord_pitches,
            duration,
            offset,
            track_params,
            pattern_params,
        )

        # Find kick events
        kick_events = [e for e in events if e[0] == KICK.midi]

        # Should have kicks on beats 0, 1, 2, 3
        kick_times = {e[1] for e in kick_events}
        assert Fraction(0) in kick_times
        assert Fraction(1) in kick_times
        assert Fraction(2) in kick_times
        assert Fraction(3) in kick_times

    def test_backbeat_only_snare(self):
        """Backbeat should only generate snare hits on beats 2 and 4."""
        chord_pitches = []
        duration = Fraction(4)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = generate_pattern(
            "backbeat", chord_pitches, duration, offset, track_params, pattern_params
        )

        # All events should be snare
        assert all(e[0] == SNARE.midi for e in events)

        # Should have snares on beat 1 and 3 (0-indexed = beats 2 and 4)
        snare_times = {e[1] for e in events}
        assert Fraction(1) in snare_times
        assert Fraction(3) in snare_times

    def test_eighth_hats_timing(self):
        """Eighth hats should generate hi-hat on eighth notes."""
        chord_pitches = []
        duration = Fraction(4)  # 4 beats
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = generate_pattern(
            "eighth_hats", chord_pitches, duration, offset, track_params, pattern_params
        )

        # Should have 8 hi-hat hits (4 beats * 2 eighths per beat)
        assert len(events) == 8

        # All should be hi-hats
        assert all(e[0] == HIHAT_CLOSED.midi for e in events)

        # Check timing - should be every half beat
        expected_times = [Fraction(i, 2) for i in range(8)]
        actual_times = [e[1] for e in events]
        assert sorted(actual_times) == expected_times

    def test_shuffle_triplet_feel(self):
        """Shuffle should use triplet timing."""
        chord_pitches = []
        duration = Fraction(4)
        offset = Fraction(0)
        track_params = {"velocity": 100, "octave_shift": 0}
        pattern_params = {}

        events = generate_pattern(
            "shuffle", chord_pitches, duration, offset, track_params, pattern_params
        )

        # Should have hi-hat events with triplet timing
        hihat_events = [e for e in events if e[0] == HIHAT_CLOSED.midi]

        # Hi-hats should be at triplet positions
        # In 4 beats, we have swung hi-hats at: 0, 2/3, 1, 5/3, 2, 8/3, 3, 11/3
        hihat_times = {e[1] for e in hihat_events}

        # Check for some triplet-based timings
        assert Fraction(0) in hihat_times  # First beat
        assert Fraction(2, 3) in hihat_times  # First swung eighth


class TestDrumMIDIChannel:
    """Test that drums are assigned to MIDI channel 10 (0-indexed channel 9)."""

    def test_rhythm_track_uses_channel_10(self):
        """Tracks with role=RHYTHM should use MIDI channel 10 (0-indexed: 9)."""
        from pypulang import I

        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, I, I, I)  # Static harmony (drums ignore it anyway)
            verse.track("drums", role=Role.RHYTHM).notes(
                [(KICK, 1 / 4), (SNARE, 1 / 4), (KICK, 1 / 4), (SNARE, 1 / 4)]
            )

        midi_file = realize_to_midi(p.to_ir())

        # Find the drums track (track 1, since track 0 is conductor)
        drums_track = midi_file.tracks[1]

        # Check that note messages use channel 9 (0-indexed = channel 10)
        note_messages = [msg for msg in drums_track if msg.type in ("note_on", "note_off")]
        assert len(note_messages) > 0
        assert all(msg.channel == 9 for msg in note_messages)

    def test_non_rhythm_track_uses_channel_0(self):
        """Tracks without role=RHYTHM should use default channel 0."""
        from pypulang import I

        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, I, I, I)
            verse.track("bass", role=Role.BASS).notes([(60, 1)])  # C4

        midi_file = realize_to_midi(p.to_ir())

        # Find the bass track
        bass_track = midi_file.tracks[1]

        # Check that note messages use channel 0
        note_messages = [msg for msg in bass_track if msg.type in ("note_on", "note_off")]
        assert len(note_messages) > 0
        assert all(msg.channel == 0 for msg in note_messages)


class TestDrumPatternIntegration:
    """Integration tests for drum patterns in full compositions."""

    def test_rock_beat_in_composition(self):
        """Test rock_beat pattern in a full composition."""
        from pypulang import I, IV, V, rock_beat

        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, V, I)
            verse.track("drums", role=Role.RHYTHM).pattern(rock_beat)

        # Should create valid MIDI
        midi_file = realize_to_midi(p.to_ir())
        assert midi_file is not None
        assert len(midi_file.tracks) == 2  # Conductor + drums

    def test_multiple_drum_patterns(self):
        """Test multiple drum patterns in different sections."""
        from pypulang import I, IV, V, four_on_floor, rock_beat, shuffle

        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, V, I)
            verse.track("drums", role=Role.RHYTHM).pattern(rock_beat)

            chorus = p.section("chorus", bars=4)
            chorus.harmony(I, IV, V, I)
            chorus.track("drums", role=Role.RHYTHM).pattern(four_on_floor)

            bridge = p.section("bridge", bars=4)
            bridge.harmony(I, IV, V, I)
            bridge.track("drums", role=Role.RHYTHM).pattern(shuffle)

        midi_file = realize_to_midi(p.to_ir())
        assert midi_file is not None

    def test_layered_drums(self):
        """Test multiple drum tracks playing simultaneously."""
        from pypulang import I, backbeat, eighth_hats

        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, I, I, I)
            verse.track("snare", role=Role.RHYTHM).pattern(backbeat)
            verse.track("hats", role=Role.RHYTHM).pattern(eighth_hats)

        midi_file = realize_to_midi(p.to_ir())
        assert midi_file is not None
        assert len(midi_file.tracks) == 3  # Conductor + 2 drum tracks
