"""
Tests for MIDI emission (Phase 1.5).

Tests that Intent IR pieces can be realized to valid MIDI files.
"""

import tempfile
from fractions import Fraction
from pathlib import Path

import mido

from pypulang import (
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
    realize_to_midi,
    save_midi,
)


class TestBasicMidiEmission:
    """Test basic MIDI file structure and metadata."""

    def test_empty_piece_creates_valid_midi(self):
        """An empty piece should still produce a valid MIDI file."""
        piece = Piece(tempo=120, key=Key("C", "major"))
        midi = realize_to_midi(piece)

        assert isinstance(midi, mido.MidiFile)
        assert midi.ticks_per_beat == 480  # Default
        # Should have at least the conductor track
        assert len(midi.tracks) >= 1

    def test_tempo_is_set_correctly(self):
        """Tempo should be converted to microseconds per beat."""
        piece = Piece(tempo=120, key=Key("C", "major"))
        midi = realize_to_midi(piece)

        # Find tempo message in conductor track
        conductor = midi.tracks[0]
        tempo_msgs = [m for m in conductor if m.type == "set_tempo"]

        assert len(tempo_msgs) == 1
        # 120 BPM = 500,000 microseconds per beat
        assert tempo_msgs[0].tempo == 500_000

    def test_tempo_60_bpm(self):
        """Test 60 BPM = 1,000,000 microseconds per beat."""
        piece = Piece(tempo=60, key=Key("C", "major"))
        midi = realize_to_midi(piece)

        conductor = midi.tracks[0]
        tempo_msgs = [m for m in conductor if m.type == "set_tempo"]
        assert tempo_msgs[0].tempo == 1_000_000

    def test_time_signature_is_set(self):
        """Time signature should be in the conductor track."""
        piece = Piece(
            tempo=120,
            key=Key("C", "major"),
            time_signature=TimeSignature(6, 8),
        )
        midi = realize_to_midi(piece)

        conductor = midi.tracks[0]
        ts_msgs = [m for m in conductor if m.type == "time_signature"]

        assert len(ts_msgs) == 1
        assert ts_msgs[0].numerator == 6
        assert ts_msgs[0].denominator == 8

    def test_custom_ticks_per_beat(self):
        """Should respect custom ticks_per_beat setting."""
        piece = Piece(tempo=120, key=Key("C", "major"))
        midi = realize_to_midi(piece, ticks_per_beat=960)

        assert midi.ticks_per_beat == 960


class TestSingleSectionMidi:
    """Test MIDI generation with a single section."""

    def test_section_with_root_quarters_pattern(self):
        """A bass track with root_quarters should produce quarter notes."""
        # Create a 4-bar section with I-IV-vi-V progression
        section = Section(
            name="verse",
            bars=4,
            harmony=Harmony(
                changes=[
                    ChordChange(Chord("I", "major"), Fraction(1)),
                    ChordChange(Chord("IV", "major"), Fraction(1)),
                    ChordChange(Chord("vi", "minor"), Fraction(1)),
                    ChordChange(Chord("V", "major"), Fraction(1)),
                ],
                duration_unit="bars",
            ),
            tracks=[
                Track(
                    name="bass",
                    role="bass",
                    content=Pattern("root_quarters"),
                    octave_shift=-2,
                    velocity=100,
                ),
            ],
        )

        piece = Piece(
            tempo=100,
            key=Key("C", "major"),
            time_signature=TimeSignature(4, 4),
            sections=[section],
        )

        midi = realize_to_midi(piece)

        # Should have conductor + 1 track
        assert len(midi.tracks) == 2

        # Check the bass track
        bass_track = midi.tracks[1]
        note_on_msgs = [m for m in bass_track if m.type == "note_on" and m.velocity > 0]

        # 4 bars * 4 beats = 16 quarter notes
        assert len(note_on_msgs) == 16

    def test_section_with_root_eighths_pattern(self):
        """Root eighths should produce twice as many notes as root quarters."""
        section = Section(
            name="verse",
            bars=2,
            harmony=Harmony(
                changes=[
                    ChordChange(Chord("I", "major"), Fraction(2)),
                ],
                duration_unit="bars",
            ),
            tracks=[
                Track(
                    name="bass",
                    role="bass",
                    content=Pattern("root_eighths"),
                    velocity=100,
                ),
            ],
        )

        piece = Piece(
            tempo=120,
            key=Key("C", "major"),
            time_signature=TimeSignature(4, 4),
            sections=[section],
        )

        midi = realize_to_midi(piece)
        bass_track = midi.tracks[1]
        note_on_msgs = [m for m in bass_track if m.type == "note_on" and m.velocity > 0]

        # 2 bars * 4 beats * 2 eighth notes per beat = 16 notes
        assert len(note_on_msgs) == 16

    def test_chord_pitches_are_correct(self):
        """Notes should have correct pitches based on chord resolution."""
        # C major chord, root quarters pattern at octave 2
        section = Section(
            name="test",
            bars=1,
            harmony=Harmony(
                changes=[
                    ChordChange(Chord("I", "major"), Fraction(1)),
                ],
                duration_unit="bars",
            ),
            tracks=[
                Track(
                    name="bass",
                    role="bass",
                    content=Pattern("root_quarters"),
                    octave_shift=-2,  # From octave 4 to octave 2
                    velocity=100,
                ),
            ],
        )

        piece = Piece(
            tempo=120,
            key=Key("C", "major"),
            time_signature=TimeSignature(4, 4),
            sections=[section],
        )

        midi = realize_to_midi(piece)
        bass_track = midi.tracks[1]
        note_on_msgs = [m for m in bass_track if m.type == "note_on" and m.velocity > 0]

        # All notes should be C2 (MIDI 36)
        # C4=60, octave_shift=-2 means C2=36
        for msg in note_on_msgs:
            assert msg.note == 36, f"Expected C2 (36), got {msg.note}"

    def test_velocity_is_applied(self):
        """Track velocity should be applied to notes."""
        section = Section(
            name="test",
            bars=1,
            harmony=Harmony(
                changes=[
                    ChordChange(Chord("I", "major"), Fraction(1)),
                ],
                duration_unit="bars",
            ),
            tracks=[
                Track(
                    name="test",
                    content=Pattern("root_quarters"),
                    velocity=80,
                ),
            ],
        )

        piece = Piece(
            tempo=120,
            key=Key("C", "major"),
            sections=[section],
        )

        midi = realize_to_midi(piece)
        track = midi.tracks[1]
        note_on_msgs = [m for m in track if m.type == "note_on" and m.velocity > 0]

        for msg in note_on_msgs:
            assert msg.velocity == 80


class TestMultiTrackMidi:
    """Test MIDI generation with multiple tracks."""

    def test_two_tracks_create_two_midi_tracks(self):
        """Multiple puLang tracks should create separate MIDI tracks."""
        section = Section(
            name="verse",
            bars=2,
            harmony=Harmony(
                changes=[
                    ChordChange(Chord("I", "major"), Fraction(2)),
                ],
                duration_unit="bars",
            ),
            tracks=[
                Track(
                    name="bass",
                    role="bass",
                    content=Pattern("root_quarters"),
                ),
                Track(
                    name="keys",
                    role="harmony",
                    content=Pattern("block_chords", {"rate": Fraction(1, 2)}),
                ),
            ],
        )

        piece = Piece(
            tempo=120,
            key=Key("C", "major"),
            sections=[section],
        )

        midi = realize_to_midi(piece)

        # Conductor + 2 tracks
        assert len(midi.tracks) == 3

    def test_muted_tracks_are_skipped(self):
        """Muted tracks should not produce MIDI output."""
        section = Section(
            name="verse",
            bars=2,
            harmony=Harmony(
                changes=[
                    ChordChange(Chord("I", "major"), Fraction(2)),
                ],
                duration_unit="bars",
            ),
            tracks=[
                Track(
                    name="bass",
                    content=Pattern("root_quarters"),
                    muted=True,  # Muted!
                ),
                Track(
                    name="keys",
                    content=Pattern("block_chords"),
                ),
            ],
        )

        piece = Piece(
            tempo=120,
            key=Key("C", "major"),
            sections=[section],
        )

        midi = realize_to_midi(piece)

        # Conductor + 1 track (bass is muted)
        assert len(midi.tracks) == 2


class TestMultipleSectionsMidi:
    """Test MIDI generation with multiple sections."""

    def test_sections_are_sequential(self):
        """Multiple sections should play one after another."""
        section1 = Section(
            name="intro",
            bars=2,
            harmony=Harmony(
                changes=[ChordChange(Chord("I", "major"), Fraction(2))],
                duration_unit="bars",
            ),
            tracks=[
                Track(name="bass", content=Pattern("root_quarters")),
            ],
        )

        section2 = Section(
            name="verse",
            bars=2,
            harmony=Harmony(
                changes=[ChordChange(Chord("V", "major"), Fraction(2))],
                duration_unit="bars",
            ),
            tracks=[
                Track(name="bass", content=Pattern("root_quarters")),
            ],
        )

        piece = Piece(
            tempo=120,
            key=Key("C", "major"),
            sections=[section1, section2],
        )

        midi = realize_to_midi(piece)
        bass_track = midi.tracks[1]
        note_on_msgs = [m for m in bass_track if m.type == "note_on" and m.velocity > 0]

        # 4 bars total * 4 beats = 16 notes
        assert len(note_on_msgs) == 16

    def test_form_controls_section_order(self):
        """The form list should control playback order."""
        intro = Section(
            name="intro",
            bars=1,
            harmony=Harmony(
                changes=[ChordChange(Chord("I", "major"), Fraction(1))],
                duration_unit="bars",
            ),
            tracks=[Track(name="bass", content=Pattern("root_quarters"))],
        )

        verse = Section(
            name="verse",
            bars=1,
            harmony=Harmony(
                changes=[ChordChange(Chord("IV", "major"), Fraction(1))],
                duration_unit="bars",
            ),
            tracks=[Track(name="bass", content=Pattern("root_quarters"))],
        )

        # Form: intro, verse, verse (3 sections)
        piece = Piece(
            tempo=120,
            key=Key("C", "major"),
            sections=[intro, verse],
            form=["intro", "verse", "verse"],
        )

        midi = realize_to_midi(piece)
        bass_track = midi.tracks[1]
        note_on_msgs = [m for m in bass_track if m.type == "note_on" and m.velocity > 0]

        # 3 sections * 1 bar * 4 beats = 12 notes
        assert len(note_on_msgs) == 12


class TestLiteralNotes:
    """Test MIDI generation with literal notes (escape hatch)."""

    def test_literal_notes_track(self):
        """Literal notes should be realized correctly."""
        section = Section(
            name="melody",
            bars=1,
            tracks=[
                Track(
                    name="melody",
                    role="melody",
                    content=Notes(
                        notes=[
                            Note(pitch=60, duration=Fraction(1, 4), offset=Fraction(0)),
                            Note(pitch=62, duration=Fraction(1, 4), offset=Fraction(1, 4)),
                            Note(pitch=64, duration=Fraction(1, 2), offset=Fraction(1, 2)),
                        ]
                    ),
                    velocity=90,
                ),
            ],
        )

        piece = Piece(
            tempo=120,
            key=Key("C", "major"),
            sections=[section],
        )

        midi = realize_to_midi(piece)
        melody_track = midi.tracks[1]
        note_on_msgs = [m for m in melody_track if m.type == "note_on" and m.velocity > 0]

        assert len(note_on_msgs) == 3
        pitches = [m.note for m in note_on_msgs]
        assert pitches == [60, 62, 64]  # C4, D4, E4

    def test_rests_are_skipped(self):
        """Rest notes (pitch=-1) should not produce MIDI events."""
        section = Section(
            name="test",
            bars=1,
            tracks=[
                Track(
                    name="test",
                    content=Notes(
                        notes=[
                            Note(pitch=60, duration=Fraction(1, 4), offset=Fraction(0)),
                            Note(pitch=-1, duration=Fraction(1, 4), offset=Fraction(1, 4)),  # Rest
                            Note(pitch=64, duration=Fraction(1, 2), offset=Fraction(1, 2)),
                        ]
                    ),
                ),
            ],
        )

        piece = Piece(
            tempo=120,
            key=Key("C", "major"),
            sections=[section],
        )

        midi = realize_to_midi(piece)
        track = midi.tracks[1]
        note_on_msgs = [m for m in track if m.type == "note_on" and m.velocity > 0]

        assert len(note_on_msgs) == 2


class TestSectionKeyOverride:
    """Test that section-level key override works."""

    def test_section_key_override(self):
        """Section key should override piece key for chord resolution."""
        # Section in G major (different from piece in C major)
        section = Section(
            name="modulation",
            bars=1,
            key=Key("G", "major"),  # Override!
            harmony=Harmony(
                changes=[ChordChange(Chord("I", "major"), Fraction(1))],
                duration_unit="bars",
            ),
            tracks=[
                Track(
                    name="bass",
                    content=Pattern("root_quarters"),
                    octave_shift=-2,
                ),
            ],
        )

        piece = Piece(
            tempo=120,
            key=Key("C", "major"),  # Piece is in C
            sections=[section],
        )

        midi = realize_to_midi(piece)
        bass_track = midi.tracks[1]
        note_on_msgs = [m for m in bass_track if m.type == "note_on" and m.velocity > 0]

        # I chord in G major at octave 2 should be G2 (MIDI 43)
        for msg in note_on_msgs:
            assert msg.note == 43, f"Expected G2 (43), got {msg.note}"


class TestFileSaving:
    """Test saving MIDI files to disk."""

    def test_save_midi_creates_file(self):
        """save_midi should create a valid MIDI file on disk."""
        section = Section(
            name="verse",
            bars=4,
            harmony=Harmony(
                changes=[
                    ChordChange(Chord("I", "major"), Fraction(1)),
                    ChordChange(Chord("IV", "major"), Fraction(1)),
                    ChordChange(Chord("vi", "minor"), Fraction(1)),
                    ChordChange(Chord("V", "major"), Fraction(1)),
                ],
                duration_unit="bars",
            ),
            tracks=[
                Track(
                    name="bass",
                    role="bass",
                    content=Pattern("root_quarters"),
                    octave_shift=-1,
                ),
            ],
        )

        piece = Piece(
            tempo=100,
            key=Key("C", "major"),
            sections=[section],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.mid"
            save_midi(piece, str(path))

            assert path.exists()

            # Should be readable by mido
            loaded = mido.MidiFile(str(path))
            assert loaded.ticks_per_beat == 480


class TestRoadmapExample:
    """Test the example from the roadmap (Phase 1 test composition)."""

    def test_phase1_example_composition(self):
        """
        The roadmap specifies this test composition:

        with piece(tempo=100, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        This test verifies it produces valid MIDI.
        """
        # Create the equivalent IR structure
        verse = Section(
            name="verse",
            bars=4,
            harmony=Harmony(
                changes=[
                    ChordChange(Chord("I", "major"), Fraction(1)),
                    ChordChange(Chord("IV", "major"), Fraction(1)),
                    ChordChange(Chord("vi", "minor"), Fraction(1)),
                    ChordChange(Chord("V", "major"), Fraction(1)),
                ],
                duration_unit="bars",
            ),
            tracks=[
                Track(
                    name="bass",
                    role="bass",
                    content=Pattern("root_quarters"),
                    octave_shift=-1,
                ),
            ],
        )

        piece = Piece(
            tempo=100,
            key=Key("C", "major"),
            time_signature=TimeSignature(4, 4),
            sections=[verse],
        )

        midi = realize_to_midi(piece)

        # Verify structure
        assert len(midi.tracks) == 2  # Conductor + bass

        # Verify tempo
        conductor = midi.tracks[0]
        tempo_msgs = [m for m in conductor if m.type == "set_tempo"]
        assert tempo_msgs[0].tempo == 600_000  # 100 BPM

        # Verify notes
        bass_track = midi.tracks[1]
        note_on_msgs = [m for m in bass_track if m.type == "note_on" and m.velocity > 0]

        # 4 bars * 4 beats = 16 quarter notes
        assert len(note_on_msgs) == 16

        # Verify pitches (at octave 3, since base is 4 with -1 shift)
        # I in C = C3 (48), IV = F3 (53), vi = A3 (57), V = G3 (55)
        expected_pitches = (
            [48] * 4  # C3 for I chord (4 beats)
            + [53] * 4  # F3 for IV chord
            + [57] * 4  # A3 for vi chord
            + [55] * 4  # G3 for V chord
        )

        actual_pitches = [m.note for m in note_on_msgs]
        assert actual_pitches == expected_pitches

        # Verify the file can be saved
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.mid"
            midi.save(str(path))
            assert path.exists()
            # Verify it's readable
            loaded = mido.MidiFile(str(path))
            assert loaded.ticks_per_beat == 480
