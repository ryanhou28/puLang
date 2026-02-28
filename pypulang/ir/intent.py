"""
Intent IR - Captures compositional intent.

This module defines the Intent IR dataclasses that represent what the composer
wants, not how it sounds. Captures harmonic, structural, and pattern-level intent.

All types are JSON-serializable for interchange with other tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Literal, Union

# -----------------------------------------------------------------------------
# Key and Time Signature
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Key:
    """
    Musical key signature.

    Attributes:
        root: Pitch class name (C, D, E, F, G, A, B with optional # or b)
        mode: Scale mode (major, minor, dorian, phrygian, lydian, mixolydian, etc.)
    """

    root: str
    mode: str = "major"

    def __post_init__(self) -> None:
        valid_roots = {
            "C",
            "D",
            "E",
            "F",
            "G",
            "A",
            "B",
            "C#",
            "D#",
            "F#",
            "G#",
            "A#",
            "Db",
            "Eb",
            "Gb",
            "Ab",
            "Bb",
        }
        if self.root not in valid_roots:
            raise ValueError(f"Invalid key root: {self.root}")

        valid_modes = {
            "major",
            "minor",
            "dorian",
            "phrygian",
            "lydian",
            "mixolydian",
            "aeolian",
            "locrian",
            "harmonic_minor",
            "melodic_minor",
        }
        if self.mode not in valid_modes:
            raise ValueError(f"Invalid mode: {self.mode}")

    @classmethod
    def parse(cls, s: str) -> Key:
        """Parse a key string like 'C major' or 'F# minor'."""
        parts = s.strip().split()
        if len(parts) == 1:
            return cls(root=parts[0], mode="major")
        elif len(parts) == 2:
            return cls(root=parts[0], mode=parts[1].lower())
        else:
            raise ValueError(f"Cannot parse key: {s}")

    def to_dict(self) -> dict[str, str]:
        return {"root": self.root, "mode": self.mode}

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> Key:
        return cls(root=d["root"], mode=d["mode"])


@dataclass(frozen=True)
class TimeSignature:
    """
    Time signature.

    Attributes:
        numerator: Beats per bar
        denominator: Note value that gets one beat (must be power of 2)
    """

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.numerator < 1:
            raise ValueError(f"Invalid numerator: {self.numerator}")
        if self.denominator < 1 or (self.denominator & (self.denominator - 1)) != 0:
            raise ValueError(f"Denominator must be power of 2: {self.denominator}")

    @property
    def beats_per_bar(self) -> Fraction:
        """Number of quarter-note beats per bar."""
        return Fraction(self.numerator * 4, self.denominator)

    @classmethod
    def parse(cls, s: str) -> TimeSignature:
        """Parse a time signature string like '4/4' or '6/8'."""
        parts = s.strip().split("/")
        if len(parts) != 2:
            raise ValueError(f"Cannot parse time signature: {s}")
        return cls(numerator=int(parts[0]), denominator=int(parts[1]))

    def to_dict(self) -> dict[str, int]:
        return {"numerator": self.numerator, "denominator": self.denominator}

    @classmethod
    def from_dict(cls, d: dict[str, int]) -> TimeSignature:
        return cls(numerator=d["numerator"], denominator=d["denominator"])


# -----------------------------------------------------------------------------
# Chord Types
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Chord:
    """
    A chord represented as a roman numeral.

    Attributes:
        numeral: Roman numeral (I-VII or i-vii)
        quality: major, minor, diminished, augmented
        extensions: List of extensions like "7", "9", "sus4", "add9"
        inversion: 0=root, 1=first, 2=second, 3=third (for 7ths)
        altered_root: 0=natural, -1=flat, +1=sharp (for bVII, #IV, etc.)
        secondary: Target for secondary dominants, e.g., "V" for V/V
    """

    numeral: str
    quality: str = "major"
    extensions: tuple[str, ...] = ()
    inversion: int = 0
    altered_root: int = 0
    secondary: str | None = None

    def __post_init__(self) -> None:
        valid_numerals = {
            "I",
            "II",
            "III",
            "IV",
            "V",
            "VI",
            "VII",
            "i",
            "ii",
            "iii",
            "iv",
            "v",
            "vi",
            "vii",
        }
        if self.numeral not in valid_numerals:
            raise ValueError(f"Invalid numeral: {self.numeral}")

        valid_qualities = {"major", "minor", "diminished", "augmented"}
        if self.quality not in valid_qualities:
            raise ValueError(f"Invalid quality: {self.quality}")

    @property
    def degree(self) -> int:
        """Return scale degree (1-7)."""
        numeral_map = {
            "I": 1,
            "II": 2,
            "III": 3,
            "IV": 4,
            "V": 5,
            "VI": 6,
            "VII": 7,
            "i": 1,
            "ii": 2,
            "iii": 3,
            "iv": 4,
            "v": 5,
            "vi": 6,
            "vii": 7,
        }
        return numeral_map[self.numeral]

    @property
    def is_uppercase(self) -> bool:
        """True if the numeral is uppercase (typically major)."""
        return self.numeral.isupper()

    def to_dict(self) -> dict[str, Any]:
        return {
            "numeral": self.numeral,
            "quality": self.quality,
            "extensions": list(self.extensions),
            "inversion": self.inversion,
            "altered_root": self.altered_root,
            "secondary": self.secondary,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Chord:
        return cls(
            numeral=d["numeral"],
            quality=d["quality"],
            extensions=tuple(d.get("extensions", [])),
            inversion=d.get("inversion", 0),
            altered_root=d.get("altered_root", 0),
            secondary=d.get("secondary"),
        )


@dataclass(frozen=True)
class ChordChange:
    """
    A chord with its duration.

    Attributes:
        chord: The chord
        duration: Duration as a Fraction (interpreted per duration_unit in Harmony)
    """

    chord: Chord
    duration: Fraction

    def to_dict(self) -> dict[str, Any]:
        return {
            "chord": self.chord.to_dict(),
            "duration": str(self.duration),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChordChange:
        return cls(
            chord=Chord.from_dict(d["chord"]),
            duration=Fraction(d["duration"]),
        )


@dataclass
class Harmony:
    """
    A chord progression.

    Attributes:
        changes: List of chord changes
        duration_unit: "bars" or "beats"
    """

    changes: list[ChordChange] = field(default_factory=list)
    duration_unit: Literal["bars", "beats"] = "bars"

    def total_duration(self) -> Fraction:
        """Total duration of all chord changes."""
        return sum((c.duration for c in self.changes), Fraction(0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "harmony",
            "duration_unit": self.duration_unit,
            "changes": [c.to_dict() for c in self.changes],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Harmony:
        return cls(
            changes=[ChordChange.from_dict(c) for c in d["changes"]],
            duration_unit=d.get("duration_unit", "bars"),
        )


# -----------------------------------------------------------------------------
# Pattern and Notes (Track Content)
# -----------------------------------------------------------------------------


@dataclass
class Pattern:
    """
    A pattern generator that produces notes from harmony context.

    Attributes:
        pattern_type: Name of the pattern (e.g., "root_quarters", "arp")
        params: Pattern-specific parameters
    """

    pattern_type: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "pattern",
            "pattern_type": self.pattern_type,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Pattern:
        return cls(
            pattern_type=d["pattern_type"],
            params=d.get("params", {}),
        )


@dataclass
class Note:
    """
    A literal note (used in the escape hatch).

    Attributes:
        pitch: MIDI pitch number (0-127), or -1 for rest
        duration: Duration in beats as a Fraction
        velocity: Override velocity (None uses track default)
        offset: Position within section in beats
    """

    pitch: int
    duration: Fraction
    velocity: int | None = None
    offset: Fraction = field(default_factory=lambda: Fraction(0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pitch": self.pitch,
            "duration": str(self.duration),
            "velocity": self.velocity,
            "offset": str(self.offset),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Note:
        return cls(
            pitch=d["pitch"],
            duration=Fraction(d["duration"]),
            velocity=d.get("velocity"),
            offset=Fraction(d.get("offset", "0")),
        )


@dataclass
class Notes:
    """
    Literal notes (the escape hatch from patterns).

    Attributes:
        notes: List of Note objects
    """

    notes: list[Note] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "notes",
            "notes": [n.to_dict() for n in self.notes],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Notes:
        return cls(notes=[Note.from_dict(n) for n in d["notes"]])


# Type alias for track content
TrackContent = Union[Pattern, Notes]


# -----------------------------------------------------------------------------
# Track
# -----------------------------------------------------------------------------


@dataclass
class Track:
    """
    A named voice/instrument within a section.

    Attributes:
        name: Track identifier
        role: Musical role (melody, bass, harmony, rhythm)
        instrument: Instrument name or MIDI program number
        content: Pattern or literal Notes
        octave_shift: Relative octave adjustment
        velocity: Base velocity (0-127)
        muted: Whether track is muted
    """

    name: str
    role: str = "harmony"
    instrument: str | int = "piano"
    content: TrackContent | None = None
    octave_shift: int = 0
    velocity: int = 100
    muted: bool = False

    def __post_init__(self) -> None:
        valid_roles = {"melody", "bass", "harmony", "rhythm"}
        if self.role not in valid_roles:
            raise ValueError(f"Invalid role: {self.role}")

    def to_dict(self) -> dict[str, Any]:
        content_dict = self.content.to_dict() if self.content else None
        return {
            "type": "track",
            "name": self.name,
            "role": self.role,
            "instrument": self.instrument,
            "content": content_dict,
            "octave_shift": self.octave_shift,
            "velocity": self.velocity,
            "muted": self.muted,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Track:
        content = None
        if d.get("content"):
            content_data = d["content"]
            if content_data.get("type") == "pattern":
                content = Pattern.from_dict(content_data)
            elif content_data.get("type") == "notes":
                content = Notes.from_dict(content_data)
        return cls(
            name=d["name"],
            role=d.get("role", "harmony"),
            instrument=d.get("instrument", "piano"),
            content=content,
            octave_shift=d.get("octave_shift", 0),
            velocity=d.get("velocity", 100),
            muted=d.get("muted", False),
        )


# -----------------------------------------------------------------------------
# Section
# -----------------------------------------------------------------------------


@dataclass
class Section:
    """
    A formal unit of the piece (verse, chorus, bridge, etc.).

    Attributes:
        name: Section identifier
        bars: Length in bars
        key: Override key (None inherits from piece)
        time_signature: Override time signature (None inherits from piece)
        harmony: Chord progression
        tracks: List of tracks in this section
    """

    name: str
    bars: int
    key: Key | None = None
    time_signature: TimeSignature | None = None
    harmony: Harmony = field(default_factory=Harmony)
    tracks: list[Track] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "section",
            "name": self.name,
            "bars": self.bars,
            "key": self.key.to_dict() if self.key else None,
            "time_signature": self.time_signature.to_dict() if self.time_signature else None,
            "harmony": self.harmony.to_dict(),
            "tracks": [t.to_dict() for t in self.tracks],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Section:
        return cls(
            name=d["name"],
            bars=d["bars"],
            key=Key.from_dict(d["key"]) if d.get("key") else None,
            time_signature=TimeSignature.from_dict(d["time_signature"])
            if d.get("time_signature")
            else None,
            harmony=Harmony.from_dict(d["harmony"]) if d.get("harmony") else Harmony(),
            tracks=[Track.from_dict(t) for t in d.get("tracks", [])],
        )


# -----------------------------------------------------------------------------
# Piece
# -----------------------------------------------------------------------------


@dataclass
class Piece:
    """
    The top-level container for a musical composition.

    Attributes:
        title: Optional title
        tempo: BPM
        key: Key signature
        time_signature: Time signature
        sections: List of sections
        form: Section names in order (None for linear order)
    """

    tempo: float = 120.0
    key: Key = field(default_factory=lambda: Key("C", "major"))
    time_signature: TimeSignature = field(default_factory=lambda: TimeSignature(4, 4))
    sections: list[Section] = field(default_factory=list)
    title: str | None = None
    form: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "piece",
            "title": self.title,
            "tempo": self.tempo,
            "key": self.key.to_dict(),
            "time_signature": self.time_signature.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "form": self.form,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Piece:
        return cls(
            title=d.get("title"),
            tempo=d.get("tempo", 120.0),
            key=Key.from_dict(d["key"]) if d.get("key") else Key("C", "major"),
            time_signature=TimeSignature.from_dict(d["time_signature"])
            if d.get("time_signature")
            else TimeSignature(4, 4),
            sections=[Section.from_dict(s) for s in d.get("sections", [])],
            form=d.get("form"),
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        import json

        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, s: str) -> Piece:
        """Deserialize from JSON string."""
        import json

        return cls.from_dict(json.loads(s))
