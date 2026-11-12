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
        bass_offset: Slash bass as semitones above the key root (0-11), or None.
            Measured from the key, so transposing the key moves it with the chord.
    """

    numeral: str
    quality: str = "major"
    extensions: tuple[str, ...] = ()
    inversion: int = 0
    altered_root: int = 0
    secondary: str | None = None
    bass_offset: int | None = None

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
            "bass_offset": self.bass_offset,
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
            bass_offset=d.get("bass_offset"),
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
        articulation: "staccato", "accent", and so on, or None
    """

    pitch: int
    duration: Fraction
    velocity: int | None = None
    offset: Fraction = field(default_factory=lambda: Fraction(0))
    articulation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pitch": self.pitch,
            "duration": str(self.duration),
            "velocity": self.velocity,
            "offset": str(self.offset),
            "articulation": self.articulation,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Note:
        return cls(
            pitch=d["pitch"],
            duration=Fraction(d["duration"]),
            velocity=d.get("velocity"),
            offset=Fraction(d.get("offset", "0")),
            articulation=d.get("articulation"),
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


@dataclass
class Melody:
    """
    A phrase of motifs in scale degrees, fitted to the harmony. See `pypulang.motifs`.

    Attributes:
        phrase: Placements separated by ";", such as "hook; hook +1; hook end 1"
        low: Lowest MIDI pitch the line goes to
        high: Highest MIDI pitch the line goes to
        fit: Whether clashing notes on strong beats move onto the chord
    """

    phrase: str
    low: int = 60
    high: int = 84
    fit: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "melody",
            "phrase": self.phrase,
            "low": self.low,
            "high": self.high,
            "fit": self.fit,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Melody:
        return cls(
            phrase=d["phrase"],
            low=d.get("low", 60),
            high=d.get("high", 84),
            fit=d.get("fit", True),
        )


# Type alias for track content
TrackContent = Union[Pattern, Notes, Melody]


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
        voicing: Name of a voicing strategy, or None for close position
    """

    name: str
    role: str = "harmony"
    instrument: str | int = "piano"
    content: TrackContent | None = None
    octave_shift: int = 0
    velocity: int = 100
    muted: bool = False
    voicing: str | None = None

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
            "voicing": self.voicing,
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
            elif content_data.get("type") == "melody":
                content = Melody.from_dict(content_data)
        return cls(
            name=d["name"],
            role=d.get("role", "harmony"),
            instrument=d.get("instrument", "piano"),
            content=content,
            octave_shift=d.get("octave_shift", 0),
            velocity=d.get("velocity", 100),
            muted=d.get("muted", False),
            voicing=d.get("voicing"),
        )


# -----------------------------------------------------------------------------
# Racks and Automation
# -----------------------------------------------------------------------------


@dataclass
class Device:
    """
    A plugin on a track.

    Attributes:
        name: Local name, which automation targets refer to
        identifier: The plugin's identifier in the DAW
        params: Published parameter name to normalised value (0..1)
        patch: A preset to start from, by the plugin's own name for it; `params`
            are written on top
    """

    name: str
    identifier: str
    params: dict[str, float] = field(default_factory=dict)
    patch: str | None = None
    # A sampler's sounds: {"file", "root", "low", "high", "gain", "pan", "one_shot"}
    sounds: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "identifier": self.identifier, "params": self.params}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Device:
        return cls(name=d["name"], identifier=d["identifier"], params=d.get("params", {}))


@dataclass
class Rack:
    """
    How a track sounds: its plugin chain, level and routing.

    A rack is written once per track, not per section. A track may have a rack and
    no notes, which is how a shared reverb bus is declared.

    Attributes:
        track: Track name
        devices: Plugins, in chain order
        volume: Fader, normalised (0.74 is unity), or None to leave it alone
        pan: -1 to 1, or None to leave it alone
        color: A colour for the DAW to show, or None
        sends: Destination track name to linear gain
    """

    track: str
    devices: list[Device] = field(default_factory=list)
    volume: float | None = None
    pan: float | None = None
    color: str | None = None
    sends: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track": self.track,
            "devices": [d.to_dict() for d in self.devices],
            "volume": self.volume,
            "pan": self.pan,
            "color": self.color,
            "sends": self.sends,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Rack:
        return cls(
            track=d["track"],
            devices=[Device.from_dict(x) for x in d.get("devices", [])],
            volume=d.get("volume"),
            pan=d.get("pan"),
            color=d.get("color"),
            sends=d.get("sends", {}),
        )


@dataclass
class AudioPlacement:
    """
    An audio file played on a track during a section.

    Attributes:
        track: Track name
        file: Path to the audio file, relative to the song
        at: Beats from the section start
        length: Beats, or None for the rest of the file
        offset: Seconds into the file to start from
        gain: Decibels
    """

    track: str
    file: str
    at: Fraction = Fraction(0)
    length: Fraction | None = None
    offset: float = 0.0
    gain: float = 0.0


@dataclass
class TempoChange:
    """
    A change of tempo inside a section.

    Attributes:
        kind: "ramp", a gradual change to `value` bpm over `length` beats (a
            ritardando or accelerando); or "hold", the `length` beats starting at
            `at` played `value` times as long (a fermata)
        at: Beats from the section's start
        length: Beats
        value: The bpm a ramp reaches, or how many times longer a hold lasts
    """

    kind: str
    at: Fraction
    length: Fraction
    value: float


@dataclass
class Fill:
    """
    A drum fill: the last `beats` of a section, or of every `every` bars, played as
    these cells on these drum tracks while the other drum tracks rest.

    Attributes:
        cells: Track name to a rhythm cell, one step per `step` beats
        beats: How long the fill is
        every: Fill at the end of every this many bars; None for the section's end only
        step: Beats per step
        keep: Drum tracks that keep playing through the fill, such as a hi-hat foot
        pitches: The MIDI note for a track that has no drum pattern in the section
        velocity: Base velocity of the fill's hits
    """

    cells: dict[str, str]
    beats: Fraction = Fraction(2)
    every: int | None = None
    step: Fraction = Fraction(1, 4)
    keep: list[str] = field(default_factory=list)
    pitches: dict[str, int] = field(default_factory=dict)
    velocity: int = 96


@dataclass
class Curve:
    """
    A parameter moving during a section.

    Attributes:
        track: Track name
        target: "<device>.<parameter>", or "mix.volume" / "mix.pan" for the fader
        points: (beats from the section start, value 0..1) pairs
    """

    track: str
    target: str
    points: list[tuple[Fraction, Fraction]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track": self.track,
            "target": self.target,
            "points": [[str(t), str(v)] for t, v in self.points],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Curve:
        return cls(
            track=d["track"],
            target=d["target"],
            points=[(Fraction(t), Fraction(v)) for t, v in d.get("points", [])],
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
        curves: Parameter automation during this section
    """

    name: str
    bars: int
    key: Key | None = None
    time_signature: TimeSignature | None = None
    harmony: Harmony = field(default_factory=Harmony)
    tracks: list[Track] = field(default_factory=list)
    curves: list[Curve] = field(default_factory=list)
    audio: list[AudioPlacement] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    tempo: float | None = None
    tempo_changes: list[TempoChange] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "section",
            "name": self.name,
            "bars": self.bars,
            "key": self.key.to_dict() if self.key else None,
            "time_signature": self.time_signature.to_dict() if self.time_signature else None,
            "harmony": self.harmony.to_dict(),
            "tracks": [t.to_dict() for t in self.tracks],
            "curves": [c.to_dict() for c in self.curves],
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
            curves=[Curve.from_dict(c) for c in d.get("curves", [])],
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
        racks: How each track sounds
        motifs: Motif names to their notes in scale degrees, for melodies to use
    """

    tempo: float = 120.0
    key: Key = field(default_factory=lambda: Key("C", "major"))
    time_signature: TimeSignature = field(default_factory=lambda: TimeSignature(4, 4))
    sections: list[Section] = field(default_factory=list)
    title: str | None = None
    form: list[str] | None = None
    racks: list[Rack] = field(default_factory=list)
    motifs: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "piece",
            "title": self.title,
            "tempo": self.tempo,
            "key": self.key.to_dict(),
            "time_signature": self.time_signature.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "form": self.form,
            "racks": [r.to_dict() for r in self.racks],
            "motifs": dict(self.motifs),
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
            racks=[Rack.from_dict(r) for r in d.get("racks", [])],
            motifs=dict(d.get("motifs", {})),
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
