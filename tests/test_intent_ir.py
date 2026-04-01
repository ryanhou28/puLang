"""Tests for Intent IR dataclasses."""

from fractions import Fraction

import pytest

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


class TestKey:
    def test_create_basic_key(self):
        key = Key("C", "major")
        assert key.root == "C"
        assert key.mode == "major"

    def test_default_mode_is_major(self):
        key = Key("G")
        assert key.mode == "major"

    def test_parse_key_string(self):
        key = Key.parse("D minor")
        assert key.root == "D"
        assert key.mode == "minor"

    def test_parse_key_string_single_word(self):
        key = Key.parse("F#")
        assert key.root == "F#"
        assert key.mode == "major"

    def test_invalid_root_raises(self):
        with pytest.raises(ValueError, match="Invalid key root"):
            Key("H", "major")

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Invalid mode"):
            Key("C", "supermajor")

    def test_key_is_frozen(self):
        key = Key("C", "major")
        with pytest.raises(AttributeError):
            key.root = "D"

    def test_key_to_dict(self):
        key = Key("Bb", "minor")
        assert key.to_dict() == {"root": "Bb", "mode": "minor"}

    def test_key_from_dict(self):
        key = Key.from_dict({"root": "F#", "mode": "dorian"})
        assert key.root == "F#"
        assert key.mode == "dorian"


class TestTimeSignature:
    def test_create_time_signature(self):
        ts = TimeSignature(4, 4)
        assert ts.numerator == 4
        assert ts.denominator == 4

    def test_beats_per_bar_4_4(self):
        ts = TimeSignature(4, 4)
        assert ts.beats_per_bar == Fraction(4)

    def test_beats_per_bar_6_8(self):
        ts = TimeSignature(6, 8)
        assert ts.beats_per_bar == Fraction(3)  # 6 eighth notes = 3 quarter beats

    def test_beats_per_bar_3_4(self):
        ts = TimeSignature(3, 4)
        assert ts.beats_per_bar == Fraction(3)

    def test_parse_time_signature(self):
        ts = TimeSignature.parse("6/8")
        assert ts.numerator == 6
        assert ts.denominator == 8

    def test_invalid_denominator_raises(self):
        with pytest.raises(ValueError, match="power of 2"):
            TimeSignature(4, 5)

    def test_time_signature_to_dict(self):
        ts = TimeSignature(3, 4)
        assert ts.to_dict() == {"numerator": 3, "denominator": 4}


class TestChord:
    def test_create_chord(self):
        chord = Chord("I", "major")
        assert chord.numeral == "I"
        assert chord.quality == "major"
        assert chord.degree == 1

    def test_minor_chord(self):
        chord = Chord("vi", "minor")
        assert chord.numeral == "vi"
        assert chord.degree == 6
        assert not chord.is_uppercase

    def test_chord_with_extensions(self):
        chord = Chord("V", "major", extensions=("7",))
        assert chord.extensions == ("7",)

    def test_chord_with_inversion(self):
        chord = Chord("I", "major", inversion=1)
        assert chord.inversion == 1

    def test_secondary_dominant(self):
        chord = Chord("V", "major", extensions=("7",), secondary="V")
        assert chord.secondary == "V"

    def test_invalid_numeral_raises(self):
        with pytest.raises(ValueError, match="Invalid numeral"):
            Chord("VIII", "major")

    def test_chord_to_dict(self):
        chord = Chord("V", "major", extensions=("7",), inversion=1)
        d = chord.to_dict()
        assert d["numeral"] == "V"
        assert d["extensions"] == ["7"]
        assert d["inversion"] == 1


class TestChordChange:
    def test_create_chord_change(self):
        chord = Chord("I", "major")
        change = ChordChange(chord, Fraction(2))
        assert change.chord == chord
        assert change.duration == Fraction(2)

    def test_chord_change_to_dict(self):
        chord = Chord("IV", "major")
        change = ChordChange(chord, Fraction(1, 2))
        d = change.to_dict()
        assert d["duration"] == "1/2"
        assert d["chord"]["numeral"] == "IV"


class TestHarmony:
    def test_create_harmony(self):
        changes = [
            ChordChange(Chord("I", "major"), Fraction(2)),
            ChordChange(Chord("IV", "major"), Fraction(2)),
        ]
        harmony = Harmony(changes=changes)
        assert len(harmony.changes) == 2
        assert harmony.duration_unit == "bars"

    def test_total_duration(self):
        changes = [
            ChordChange(Chord("I", "major"), Fraction(2)),
            ChordChange(Chord("IV", "major"), Fraction(2)),
            ChordChange(Chord("V", "major"), Fraction(4)),
        ]
        harmony = Harmony(changes=changes)
        assert harmony.total_duration() == Fraction(8)

    def test_harmony_to_dict(self):
        changes = [ChordChange(Chord("I", "major"), Fraction(1))]
        harmony = Harmony(changes=changes, duration_unit="beats")
        d = harmony.to_dict()
        assert d["type"] == "harmony"
        assert d["duration_unit"] == "beats"


class TestPattern:
    def test_create_pattern(self):
        pattern = Pattern("root_quarters")
        assert pattern.pattern_type == "root_quarters"
        assert pattern.params == {}

    def test_pattern_with_params(self):
        pattern = Pattern("arp", params={"direction": "up", "rate": "1/16"})
        assert pattern.params["direction"] == "up"

    def test_pattern_to_dict(self):
        pattern = Pattern("block_chords", params={"rate": "1/2"})
        d = pattern.to_dict()
        assert d["type"] == "pattern"
        assert d["pattern_type"] == "block_chords"


class TestNotes:
    def test_create_note(self):
        note = Note(pitch=60, duration=Fraction(1, 4))
        assert note.pitch == 60
        assert note.duration == Fraction(1, 4)
        assert note.velocity is None
        assert note.offset == Fraction(0)

    def test_note_with_velocity(self):
        note = Note(pitch=64, duration=Fraction(1, 2), velocity=100)
        assert note.velocity == 100

    def test_rest_note(self):
        rest = Note(pitch=-1, duration=Fraction(1, 4))
        assert rest.pitch == -1

    def test_notes_container(self):
        notes = Notes(
            notes=[
                Note(60, Fraction(1, 4)),
                Note(62, Fraction(1, 4), offset=Fraction(1, 4)),
            ]
        )
        assert len(notes.notes) == 2

    def test_notes_to_dict(self):
        notes = Notes(notes=[Note(60, Fraction(1, 4))])
        d = notes.to_dict()
        assert d["type"] == "notes"
        assert len(d["notes"]) == 1


class TestTrack:
    def test_create_track(self):
        track = Track(name="bass", role="bass")
        assert track.name == "bass"
        assert track.role == "bass"
        assert track.velocity == 100

    def test_track_with_pattern(self):
        pattern = Pattern("root_quarters")
        track = Track(name="bass", role="bass", content=pattern)
        assert track.content == pattern

    def test_track_with_octave_shift(self):
        track = Track(name="bass", role="bass", octave_shift=-2)
        assert track.octave_shift == -2

    def test_invalid_role_raises(self):
        with pytest.raises(ValueError, match="Invalid role"):
            Track(name="test", role="invalid_role")

    def test_track_to_dict(self):
        pattern = Pattern("root_eighths")
        track = Track(name="bass", role="bass", content=pattern, octave_shift=-2)
        d = track.to_dict()
        assert d["type"] == "track"
        assert d["name"] == "bass"
        assert d["content"]["pattern_type"] == "root_eighths"


class TestSection:
    def test_create_section(self):
        section = Section(name="verse", bars=8)
        assert section.name == "verse"
        assert section.bars == 8
        assert section.key is None  # Inherits from piece

    def test_section_with_harmony(self):
        harmony = Harmony(
            changes=[
                ChordChange(Chord("I", "major"), Fraction(2)),
                ChordChange(Chord("IV", "major"), Fraction(2)),
            ]
        )
        section = Section(name="verse", bars=4, harmony=harmony)
        assert len(section.harmony.changes) == 2

    def test_section_with_tracks(self):
        track = Track(name="bass", role="bass")
        section = Section(name="verse", bars=8, tracks=[track])
        assert len(section.tracks) == 1

    def test_section_with_key_override(self):
        section = Section(name="bridge", bars=8, key=Key("G", "major"))
        assert section.key.root == "G"

    def test_section_to_dict(self):
        section = Section(name="intro", bars=4)
        d = section.to_dict()
        assert d["type"] == "section"
        assert d["name"] == "intro"
        assert d["bars"] == 4


class TestPiece:
    def test_create_piece_defaults(self):
        piece = Piece()
        assert piece.tempo == 120.0
        assert piece.key.root == "C"
        assert piece.time_signature.numerator == 4

    def test_create_piece_with_params(self):
        piece = Piece(
            title="My Song",
            tempo=100,
            key=Key("G", "major"),
            time_signature=TimeSignature(3, 4),
        )
        assert piece.title == "My Song"
        assert piece.tempo == 100
        assert piece.key.root == "G"

    def test_piece_with_sections(self):
        sections = [
            Section(name="verse", bars=8),
            Section(name="chorus", bars=8),
        ]
        piece = Piece(sections=sections)
        assert len(piece.sections) == 2

    def test_piece_with_form(self):
        piece = Piece(form=["verse", "chorus", "verse", "chorus"])
        assert piece.form == ["verse", "chorus", "verse", "chorus"]

    def test_piece_to_dict(self):
        piece = Piece(title="Test", tempo=120)
        d = piece.to_dict()
        assert d["type"] == "piece"
        assert d["title"] == "Test"
        assert d["tempo"] == 120

    def test_piece_roundtrip_json(self):
        # Create a complete piece
        harmony = Harmony(
            changes=[
                ChordChange(Chord("I", "major"), Fraction(2)),
                ChordChange(Chord("IV", "major"), Fraction(2)),
                ChordChange(Chord("vi", "minor"), Fraction(2)),
                ChordChange(Chord("V", "major"), Fraction(2)),
            ]
        )
        track = Track(
            name="bass",
            role="bass",
            content=Pattern("root_quarters"),
            octave_shift=-1,
        )
        section = Section(name="verse", bars=8, harmony=harmony, tracks=[track])
        piece = Piece(
            title="Test Song",
            tempo=100,
            key=Key("C", "major"),
            sections=[section],
        )

        # Serialize to JSON
        json_str = piece.to_json()

        # Deserialize back
        piece2 = Piece.from_json(json_str)

        # Verify roundtrip
        assert piece2.title == "Test Song"
        assert piece2.tempo == 100
        assert piece2.key.root == "C"
        assert len(piece2.sections) == 1
        assert piece2.sections[0].name == "verse"
        assert len(piece2.sections[0].harmony.changes) == 4
        assert piece2.sections[0].tracks[0].name == "bass"
        assert piece2.sections[0].tracks[0].content.pattern_type == "root_quarters"
