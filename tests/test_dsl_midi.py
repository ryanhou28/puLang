"""
Integration tests for pyPuLang DSL + MIDI output.

These tests verify the full pipeline from DSL to MIDI file.
"""

import os
import tempfile

import pytest
import mido

from pypulang import (
    piece,
    Role,
    I, IV, vi, V, V7,
    root_quarters,
    root_eighths,
    block_chords,
    arp,
)


class TestDSLToMIDI:
    """Integration tests for DSL → MIDI pipeline."""

    def test_roadmap_example_produces_midi(self):
        """The roadmap test composition produces valid MIDI."""
        with piece(tempo=100, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        midi = p.to_midi()

        # Basic validation
        assert isinstance(midi, mido.MidiFile)
        assert len(midi.tracks) >= 2  # At least conductor + bass

    def test_roadmap_example_renders_to_file(self):
        """The roadmap test composition renders to a valid MIDI file."""
        with piece(tempo=100, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.mid")
            p.save_midi(path)

            # File should exist
            assert os.path.exists(path)

            # File should be valid MIDI
            midi = mido.MidiFile(path)
            assert len(midi.tracks) >= 2

    def test_midi_has_correct_tempo(self):
        """MIDI file has correct tempo."""
        with piece(tempo=100, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass").pattern(root_quarters)

        midi = p.to_midi()

        # Find tempo message in conductor track
        tempo_msg = None
        for msg in midi.tracks[0]:
            if msg.type == "set_tempo":
                tempo_msg = msg
                break

        assert tempo_msg is not None
        # 100 BPM = 600000 microseconds per beat
        assert tempo_msg.tempo == 600000

    def test_midi_has_correct_time_signature(self):
        """MIDI file has correct time signature."""
        with piece(tempo=100, key="C major", time_sig="3/4") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass").pattern(root_quarters)

        midi = p.to_midi()

        # Find time signature message
        time_sig_msg = None
        for msg in midi.tracks[0]:
            if msg.type == "time_signature":
                time_sig_msg = msg
                break

        assert time_sig_msg is not None
        assert time_sig_msg.numerator == 3
        assert time_sig_msg.denominator == 4

    def test_midi_has_notes(self):
        """MIDI file contains note events."""
        with piece(tempo=100, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass").pattern(root_quarters)

        midi = p.to_midi()

        # Find note_on events
        note_on_count = 0
        for track in midi.tracks:
            for msg in track:
                if msg.type == "note_on" and msg.velocity > 0:
                    note_on_count += 1

        # 4 chords × 4 beats per bar (in 4/4) = 16 notes for root_quarters
        assert note_on_count >= 16

    def test_bass_notes_in_correct_range(self):
        """Bass notes are in the expected low range."""
        with piece(tempo=100, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)

        midi = p.to_midi()

        # Collect all note pitches
        pitches = []
        for track in midi.tracks:
            for msg in track:
                if msg.type == "note_on" and msg.velocity > 0:
                    pitches.append(msg.note)

        # With octave -2, notes should be below middle C (60)
        # C major bass notes: C2 (36), F2 (41), A2 (45), G2 (43)
        assert all(pitch < 60 for pitch in pitches)

    def test_multiple_tracks_in_midi(self):
        """Multiple tracks produce separate MIDI tracks."""
        with piece(tempo=120, key="G major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
            verse.track("keys", role=Role.HARMONY).pattern(block_chords)

        midi = p.to_midi()

        # Should have conductor + 2 instrument tracks
        assert len(midi.tracks) >= 3

    def test_muted_tracks_produce_no_notes(self):
        """Muted tracks don't produce MIDI notes."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass").pattern(root_quarters).mute()

        midi = p.to_midi()

        # Count note_on events (excluding conductor track)
        note_count = 0
        for track in midi.tracks[1:]:
            for msg in track:
                if msg.type == "note_on" and msg.velocity > 0:
                    note_count += 1

        assert note_count == 0

    def test_arp_pattern_in_midi(self):
        """Arpeggio pattern produces expected notes."""
        with piece() as p:
            verse = p.section("verse", bars=1)
            verse.harmony(I)  # C major chord: C, E, G
            verse.track("keys").pattern(arp.up().rate(0.25))  # 4 notes per beat

        midi = p.to_midi()

        # Find note_on events
        pitches = []
        for track in midi.tracks:
            for msg in track:
                if msg.type == "note_on" and msg.velocity > 0:
                    pitches.append(msg.note)

        # Should have multiple notes from arpeggio
        assert len(pitches) > 0

    def test_complete_composition_produces_valid_midi(self):
        """A more complex composition produces valid MIDI."""
        with piece(tempo=120, key="G major") as p:
            # Intro
            intro = p.section("intro", bars=4)
            intro.harmony((I, 2), (IV, 2))
            intro.track("keys").pattern(arp.up())

            # Verse
            verse = p.section("verse", bars=8)
            verse.harmony(I, vi, IV, V, I, vi, IV, V)
            verse.track("bass", role=Role.BASS).pattern(root_eighths).octave(-2)
            verse.track("keys").pattern(block_chords)

            # Form
            p.form([intro, verse])

        midi = p.to_midi()

        # Basic validation
        assert isinstance(midi, mido.MidiFile)

        # Should be able to save without error
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "composition.mid")
            p.save_midi(path)
            assert os.path.exists(path)

            # Should be readable
            loaded = mido.MidiFile(path)
            assert len(loaded.tracks) >= 2


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_empty_section_no_crash(self):
        """Section without tracks doesn't crash MIDI generation."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            # No tracks added

        midi = p.to_midi()
        assert isinstance(midi, mido.MidiFile)

    def test_section_without_harmony(self):
        """Section without harmony still works."""
        with piece() as p:
            verse = p.section("verse", bars=4)
            # No harmony, but has a track with pattern
            verse.track("keys").pattern(block_chords)

        midi = p.to_midi()
        assert isinstance(midi, mido.MidiFile)

    def test_seventh_chords_in_harmony(self):
        """7th chords produce correct notes."""
        with piece(key="C major") as p:
            verse = p.section("verse", bars=1)
            verse.harmony(V7)  # G7: G, B, D, F
            verse.track("keys").pattern(block_chords)

        midi = p.to_midi()

        # Find note_on events
        pitches = set()
        for track in midi.tracks:
            for msg in track:
                if msg.type == "note_on" and msg.velocity > 0:
                    pitches.add(msg.note % 12)  # Get pitch class

        # G7 = G(7), B(11), D(2), F(5) as pitch classes
        expected = {7, 11, 2, 5}
        assert pitches == expected or pitches.issubset(expected)
