"""
pyPuLang DSL - Python-embedded domain-specific language for music composition.

This module provides the user-facing API for composing music:
- piece() context manager
- Roman numeral chord constants (I, II, III, IV, V, VI, VII)
- Role enum (MELODY, BASS, HARMONY, RHYTHM)
- Pattern singletons (root_quarters, etc.)
- Builder pattern for sections and tracks
"""

from __future__ import annotations

import copy
from dataclasses import replace
from enum import Enum
from fractions import Fraction
from typing import TYPE_CHECKING, Any, Union

from pypulang.harmony import parse_chart
from pypulang.ir.intent import (
    Chord,
    ChordChange,
    Curve,
    Device,
    Harmony,
    Key,
    Note,
    Notes,
    Pattern,
    Piece,
    Rack,
    Section,
    TimeSignature,
    Track,
    TrackContent,
)
from pypulang.lines import parse_line
from pypulang.reharm import reharmonize as reharmonize_changes
from pypulang.reharm import transposed_key

if TYPE_CHECKING:
    import mido

    from pypulang.playback.instruments import InstrumentBank
    from pypulang.playback.protocols import PlaybackBackend, PlaybackHandle


# -----------------------------------------------------------------------------
# Role Enum
# -----------------------------------------------------------------------------


class Role(Enum):
    """Musical roles for tracks."""

    MELODY = "melody"
    BASS = "bass"
    HARMONY = "harmony"
    RHYTHM = "rhythm"


# -----------------------------------------------------------------------------
# Roman Numeral Chords
# -----------------------------------------------------------------------------


class RomanNumeral:
    """
    A roman numeral chord that can be used in harmony() calls.

    Supports method chaining for modifiers:
        I, IV, V7, vi.dim(), V.inv(1)
    """

    def __init__(
        self,
        numeral: str,
        quality: str = "major",
        extensions: tuple[str, ...] = (),
        inversion: int = 0,
        altered_root: int = 0,
        secondary: str | None = None,
    ):
        self._numeral = numeral
        self._quality = quality
        self._extensions = extensions
        self._inversion = inversion
        self._altered_root = altered_root
        self._secondary = secondary

    def to_chord(self) -> Chord:
        """Convert to an IR Chord object."""
        return Chord(
            numeral=self._numeral,
            quality=self._quality,
            extensions=self._extensions,
            inversion=self._inversion,
            altered_root=self._altered_root,
            secondary=self._secondary,
        )

    def _copy(self, **kwargs: Any) -> RomanNumeral:
        """Create a copy with updated attributes."""
        return RomanNumeral(
            numeral=kwargs.get("numeral", self._numeral),
            quality=kwargs.get("quality", self._quality),
            extensions=kwargs.get("extensions", self._extensions),
            inversion=kwargs.get("inversion", self._inversion),
            altered_root=kwargs.get("altered_root", self._altered_root),
            secondary=kwargs.get("secondary", self._secondary),
        )

    # Quality modifiers
    def dim(self) -> RomanNumeral:
        """Make diminished chord."""
        return self._copy(quality="diminished")

    def aug(self) -> RomanNumeral:
        """Make augmented chord."""
        return self._copy(quality="augmented")

    def maj(self) -> RomanNumeral:
        """Make major chord (explicit)."""
        return self._copy(quality="major")

    def min(self) -> RomanNumeral:
        """Make minor chord (explicit)."""
        return self._copy(quality="minor")

    # Extension modifiers
    def ext(self, *tokens: str) -> RomanNumeral:
        """Add chord tokens by name, such as V.ext("7", "b9", "#11")."""
        return self._copy(extensions=self._extensions + tokens)

    def add7(self) -> RomanNumeral:
        """Add dominant 7th."""
        return self._copy(extensions=self._extensions + ("7",))

    def maj7(self) -> RomanNumeral:
        """Add major 7th."""
        return self._copy(extensions=self._extensions + ("maj7",))

    def min7(self) -> RomanNumeral:
        """Add minor 7th."""
        return self._copy(extensions=self._extensions + ("min7",))

    def add9(self) -> RomanNumeral:
        """Add 9th extension."""
        return self._copy(extensions=self._extensions + ("add9",))

    def add11(self) -> RomanNumeral:
        """Add 11th extension."""
        return self._copy(extensions=self._extensions + ("add11",))

    def sus2(self) -> RomanNumeral:
        """Suspended 2nd."""
        return self._copy(extensions=self._extensions + ("sus2",))

    def sus4(self) -> RomanNumeral:
        """Suspended 4th."""
        return self._copy(extensions=self._extensions + ("sus4",))

    # Inversion
    def inv(self, n: int) -> RomanNumeral:
        """Set inversion (0=root, 1=first, 2=second, 3=third)."""
        if n < 0 or n > 3:
            raise ValueError(f"Inversion must be 0-3, got {n}")
        return self._copy(inversion=n)

    # Altered root
    def flat(self) -> RomanNumeral:
        """Flat the root (e.g., bVII)."""
        return self._copy(altered_root=-1)

    def sharp(self) -> RomanNumeral:
        """Sharp the root (e.g., #IV)."""
        return self._copy(altered_root=1)

    # Secondary dominants
    def of(self, target: RomanNumeral | str) -> RomanNumeral:
        """
        Create a secondary dominant.

        Usage: V.of(V) for V/V, V.of(vi) for V/vi
        """
        if isinstance(target, RomanNumeral):
            target_numeral = target._numeral
        else:
            target_numeral = target
        return self._copy(secondary=target_numeral)

    def __repr__(self) -> str:
        parts = []
        if self._altered_root == -1:
            parts.append("b")
        elif self._altered_root == 1:
            parts.append("#")
        parts.append(self._numeral)

        if self._quality == "diminished":
            parts.append("°")
        elif self._quality == "augmented":
            parts.append("+")

        for ext in self._extensions:
            parts.append(ext)

        if self._secondary:
            parts.append(f"/{self._secondary}")

        if self._inversion:
            parts.append(f"(inv{self._inversion})")

        return "".join(parts)


def _make_roman(numeral: str, quality: str) -> RomanNumeral:
    """Create a RomanNumeral with the given numeral and quality."""
    return RomanNumeral(numeral=numeral, quality=quality)


# Major roman numerals
I = _make_roman("I", "major")
II = _make_roman("II", "major")
III = _make_roman("III", "major")
IV = _make_roman("IV", "major")
V = _make_roman("V", "major")
VI = _make_roman("VI", "major")
VII = _make_roman("VII", "major")

# Minor roman numerals (lowercase)
i = _make_roman("i", "minor")
ii = _make_roman("ii", "minor")
iii = _make_roman("iii", "minor")
iv = _make_roman("iv", "minor")
v = _make_roman("v", "minor")
vi = _make_roman("vi", "minor")
vii = _make_roman("vii", "minor")

# Common 7th chords as convenience
I7 = I.add7()
II7 = II.add7()
III7 = III.add7()
IV7 = IV.add7()
V7 = V.add7()
VI7 = VI.add7()
VII7 = VII.add7()

Imaj7 = I.maj7()
IVmaj7 = IV.maj7()

ii7 = ii.add7()
iii7 = iii.add7()
vi7 = vi.add7()
vii7 = vii.add7()


# -----------------------------------------------------------------------------
# Pattern Singletons
# -----------------------------------------------------------------------------


class PatternBuilder:
    """
    A pattern singleton that can be used in track.pattern() calls.

    Supports both direct use and builder-style configuration:
        track.pattern(root_quarters)
        track.pattern(arp("up"))
        track.pattern(arp.up().rate(1/16))
    """

    def __init__(self, pattern_type: str, **default_params: Any):
        self._pattern_type = pattern_type
        self._params: dict[str, Any] = dict(default_params)

    def __call__(self, *args: Any, **kwargs: Any) -> PatternBuilder:
        """Create a new PatternBuilder with parameters."""
        new_params = dict(self._params)

        # Handle positional args based on pattern type
        if self._pattern_type == "arp" and args:
            new_params["direction"] = args[0]
        elif args:
            # Generic first-positional handling
            new_params["value"] = args[0]

        new_params.update(kwargs)
        return PatternBuilder(self._pattern_type, **new_params)

    def to_pattern(self) -> Pattern:
        """Convert to an IR Pattern object."""
        return Pattern(pattern_type=self._pattern_type, params=self._params)

    # Common builder methods
    def rate(self, value: float | Fraction) -> PatternBuilder:
        """Set the rate (note subdivision)."""
        new_params = dict(self._params)
        new_params["rate"] = float(value) if isinstance(value, Fraction) else value
        return PatternBuilder(self._pattern_type, **new_params)

    def velocity(self, value: int) -> PatternBuilder:
        """Set velocity for the pattern."""
        new_params = dict(self._params)
        new_params["velocity"] = value
        return PatternBuilder(self._pattern_type, **new_params)

    def octave(self, value: int) -> PatternBuilder:
        """Set octave shift for the pattern."""
        new_params = dict(self._params)
        new_params["octave_shift"] = value
        return PatternBuilder(self._pattern_type, **new_params)

    # Arp-specific builders
    def up(self) -> PatternBuilder:
        """Arpeggio direction: up."""
        new_params = dict(self._params)
        new_params["direction"] = "up"
        return PatternBuilder(self._pattern_type, **new_params)

    def down(self) -> PatternBuilder:
        """Arpeggio direction: down."""
        new_params = dict(self._params)
        new_params["direction"] = "down"
        return PatternBuilder(self._pattern_type, **new_params)

    def updown(self) -> PatternBuilder:
        """Arpeggio direction: up then down."""
        new_params = dict(self._params)
        new_params["direction"] = "updown"
        return PatternBuilder(self._pattern_type, **new_params)

    def octaves(self, n: int) -> PatternBuilder:
        """Set number of octaves for arpeggio."""
        new_params = dict(self._params)
        new_params["octaves"] = n
        return PatternBuilder(self._pattern_type, **new_params)

    def __repr__(self) -> str:
        if self._params:
            params_str = ", ".join(f"{k}={v!r}" for k, v in self._params.items())
            return f"{self._pattern_type}({params_str})"
        return self._pattern_type


def device(name: str, identifier: str, **params: float) -> Device:
    """A plugin for a rack. Parameter names with spaces go through `params`."""
    return Device(name=name, identifier=identifier, params=dict(params))


# Pattern singletons
root_quarters = PatternBuilder("root_quarters")
root_eighths = PatternBuilder("root_eighths")
root_fifths = PatternBuilder("root_fifths")
block_chords = PatternBuilder("block_chords")
arp = PatternBuilder("arp", direction="up")

# Drum patterns (Phase 2.5)
rock_beat = PatternBuilder("rock_beat")
four_on_floor = PatternBuilder("four_on_floor")
backbeat = PatternBuilder("backbeat")
eighth_hats = PatternBuilder("eighth_hats")
shuffle = PatternBuilder("shuffle")

# Patterns that see the chord, the next chord, and the bar
grid = PatternBuilder("grid")
hits = PatternBuilder("hits")
riff = PatternBuilder("riff")
walking_bass = PatternBuilder("walking_bass")
comp = PatternBuilder("comp")
snare_roll = PatternBuilder("snare_roll")


# -----------------------------------------------------------------------------
# Track Builder
# -----------------------------------------------------------------------------


# Parameters that hold a note value, and so reach the IR as beats.
_NOTE_VALUE_PARAMS = ("rate", "hihat_rate", "step")


def note_value_to_beats(value: Fraction | float | int | str) -> Fraction:
    """
    Convert a written note value to quarter-note beats, the unit of the IR.

    The DSL speaks in note values: 1/4 is a quarter note and 1/16 a sixteenth.
    A float such as 1/3 is read as the fraction it stands for, including when
    `note()` has already turned it into a Fraction with a huge denominator.
    """
    return Fraction(value).limit_denominator(3840) * 4


class TrackBuilder:
    """
    Builder for creating tracks with method chaining.

    Usage:
        section.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)
        section.track("melody").notes([(C4, 1/4), (E4, 1/4), rest(1/4), (G4, 1/4)])
    """

    def __init__(
        self,
        name: str,
        section: SectionBuilder,
        role: Role = Role.HARMONY,
        instrument: str | int = "piano",
    ):
        self._name = name
        self._section = section
        self._role = role
        self._instrument = instrument
        self._content: TrackContent | None = None
        self._octave_shift: int = 0
        self._velocity: int = 100
        self._muted: bool = False
        self._voicing: str | None = None

    def pattern(
        self, pattern: PatternBuilder | str, **kwargs: Any
    ) -> TrackBuilder:
        """Set the pattern for this track."""
        if isinstance(pattern, str):
            self._content = Pattern(pattern_type=pattern, params=kwargs)
        elif isinstance(pattern, PatternBuilder):
            # Merge any additional kwargs
            if kwargs:
                pattern = pattern(**kwargs)
            self._content = pattern.to_pattern()
        else:
            raise TypeError(f"Expected PatternBuilder or str, got {type(pattern)}")
        return self

    def notes(self, note_list: list[Any]) -> TrackBuilder:
        """
        Set literal notes for this track (escape hatch from patterns).

        Args:
            note_list: List of notes. Each item can be:
                - (pitch, duration) tuple: e.g., (C4, 1/4)
                - (pitch, duration, velocity) tuple: e.g., (C4, 1/4, 100)
                - NoteSpec from note() function: e.g., note(C4, 1/4, velocity=100)
                - ChordSpec from chord() function: e.g., chord([C4, E4, G4], 1/2)
                - Rest from rest() function: e.g., rest(1/4)

        Returns:
            self for method chaining

        Example:
            from pypulang.pitches import *

            track.notes([
                (D5, 1/4), (E5, 1/4), (G5, 1/2),
                rest(1/4),
                note(A5, 1/4, velocity=100),
                chord([C5, E5, G5], 1/2),
            ])
        """
        # Import here to avoid circular imports
        from pypulang.pitches import ChordSpec, NoteSpec

        ir_notes: list[Note] = []
        current_offset = Fraction(0)

        for item in note_list:
            if isinstance(item, NoteSpec):
                # NoteSpec from note() or rest()
                beats = note_value_to_beats(item.duration)
                ir_notes.append(Note(
                    pitch=item.pitch,
                    duration=beats,
                    velocity=item.velocity,
                    offset=current_offset,
                ))
                current_offset += beats

            elif isinstance(item, ChordSpec):
                # ChordSpec from chord() - multiple simultaneous notes
                beats = note_value_to_beats(item.duration)
                for pitch in item.pitches:
                    ir_notes.append(Note(
                        pitch=pitch,
                        duration=beats,
                        velocity=item.velocity,
                        offset=current_offset,
                    ))
                current_offset += beats

            elif isinstance(item, tuple):
                # Tuple syntax: (pitch, duration) or (pitch, duration, velocity)
                if len(item) == 2:
                    pitch, duration = item
                    velocity = None
                elif len(item) == 3:
                    pitch, duration, velocity = item
                else:
                    raise ValueError(f"Invalid note tuple: {item}. Expected 2 or 3 elements.")

                beats = note_value_to_beats(duration)
                ir_notes.append(Note(
                    pitch=int(pitch),
                    duration=beats,
                    velocity=velocity,
                    offset=current_offset,
                ))
                current_offset += beats

            else:
                raise TypeError(
                    f"Invalid note type: {type(item)}. "
                    "Expected tuple, NoteSpec, or ChordSpec."
                )

        self._content = Notes(notes=ir_notes)
        return self

    def line(self, text: str, velocity: int | None = None) -> TrackBuilder:
        """
        Set literal notes from melody notation. See `pypulang.lines`.

        Args:
            text: For example "a4/8 c5 e5/4. r/8 | g5/2 f5/4 e5"
            velocity: Base velocity (defaults to the track's)

        Example:
            track.line("d5/8 f5 a5/4 | c6/2. r/4")
        """
        section = self._section
        meter = section._time_signature or section._piece._time_signature
        base = velocity if velocity is not None else self._velocity
        notes = []
        for n in parse_line(text, meter.beats_per_bar):
            notes.append(
                Note(
                    pitch=n.pitch,
                    duration=n.dur,
                    velocity=max(1, min(127, int(base * n.velocity_scale))),
                    offset=n.start,
                    articulation=n.articulation,
                )
            )
        self._content = Notes(notes=notes)
        return self

    def voicing(
        self, name: str, low: int | None = None, high: int | None = None
    ) -> TrackBuilder:
        """
        Choose how this track voices its chords.

        Args:
            name: A strategy from `pypulang.voicing`: close, shell, rootless, drop2,
                quartal, upper_structure, wide
            low: Lowest MIDI pitch, such as E3
            high: Highest MIDI pitch

        The `voice-lead` pass picks the voicing of each chord so that the whole
        progression moves as little as it can.
        """
        self._voicing = name if low is None else f"{name}({int(low)},{int(high)})"
        return self

    def octave(self, n: int) -> TrackBuilder:
        """Set octave shift for this track."""
        self._octave_shift = n
        return self

    def velocity(self, v: int) -> TrackBuilder:
        """Set velocity for this track (0-127)."""
        if not 0 <= v <= 127:
            raise ValueError(f"Velocity must be 0-127, got {v}")
        self._velocity = v
        return self

    def mute(self) -> TrackBuilder:
        """Mute this track."""
        self._muted = True
        return self

    def unmute(self) -> TrackBuilder:
        """Unmute this track."""
        self._muted = False
        return self

    def _ir_content(self) -> TrackContent | None:
        """The track's content with note values converted to beats."""
        if not isinstance(self._content, Pattern):
            return self._content
        params = dict(self._content.params)
        for name in _NOTE_VALUE_PARAMS:
            if name in params:
                params[name] = note_value_to_beats(params[name])
        return Pattern(pattern_type=self._content.pattern_type, params=params)

    def _to_ir(self) -> Track:
        """Convert to IR Track object."""
        return Track(
            name=self._name,
            role=self._role.value,
            instrument=self._instrument,
            content=self._ir_content(),
            octave_shift=self._octave_shift,
            velocity=self._velocity,
            muted=self._muted,
            voicing=self._voicing,
        )


# -----------------------------------------------------------------------------
# Section Builder
# -----------------------------------------------------------------------------

# Type for chord arguments in harmony()
ChordArg = Union[RomanNumeral, tuple[RomanNumeral, int], tuple[RomanNumeral, float]]


class SectionBuilder:
    """
    Builder for creating sections with method chaining.

    Usage:
        verse = p.section("verse", bars=8)
        verse.harmony(I, IV, vi, V)
        verse.track("bass", role=Role.BASS).pattern(root_quarters)
    """

    def __init__(
        self,
        name: str,
        bars: int,
        piece: PieceBuilder,
        key: Key | None = None,
        time_signature: TimeSignature | None = None,
    ):
        self._name = name
        self._bars = bars
        self._piece = piece
        self._key = key
        self._time_signature = time_signature
        self._harmony: Harmony = Harmony()
        self._tracks: list[TrackBuilder] = []
        self._curves: list[Curve] = []

    @property
    def name(self) -> str:
        """Get section name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set section name."""
        self._name = value

    def harmony(self, *chords: ChordArg) -> SectionBuilder:
        """
        Set the chord progression for this section.

        Args:
            *chords: Roman numerals, optionally with durations as tuples.
                     Examples: I, IV, vi, V
                              (I, 2), (IV, 1), (vi, 1), (V, 4)
        """
        changes = []

        # Calculate default duration if no explicit durations given
        has_explicit_durations = any(isinstance(c, tuple) for c in chords)

        if has_explicit_durations:
            for chord_arg in chords:
                if isinstance(chord_arg, tuple):
                    roman, duration = chord_arg
                    changes.append(
                        ChordChange(
                            chord=roman.to_chord(),
                            duration=Fraction(duration),
                        )
                    )
                else:
                    # Default duration of 1 bar
                    changes.append(
                        ChordChange(
                            chord=chord_arg.to_chord(),
                            duration=Fraction(1),
                        )
                    )
        else:
            # Equal duration: divide bars by number of chords
            duration_per_chord = Fraction(self._bars, len(chords))
            for chord_arg in chords:
                changes.append(
                    ChordChange(
                        chord=chord_arg.to_chord(),
                        duration=duration_per_chord,
                    )
                )

        self._harmony = Harmony(changes=changes, duration_unit="bars")
        return self

    def chart(self, chart: str) -> SectionBuilder:
        """
        Set the harmony from a chord chart, one bar between each "|".

        Chords in a bar share it equally and "%" repeats the previous bar. A chart
        shorter than the section loops until the section is full, so a four-bar
        vamp in a sixteen-bar section plays four times.

        Example:
            section.chart("Dm9 G13 | Cmaj9 | Em7 A7b13 | Dm9 G7alt")
        """
        key = self._key or self._piece._key
        parsed = parse_chart(chart, key)
        bars_in_chart = sum(Fraction(*fraction) for _, fraction in parsed)
        changes = []
        filled = Fraction(0)
        while filled < self._bars:
            for chord, fraction in parsed:
                if filled >= self._bars:
                    break
                duration = min(Fraction(*fraction), self._bars - filled)
                changes.append(ChordChange(chord=chord, duration=duration))
                filled += duration
            if bars_in_chart == 0:
                break
        self._harmony = Harmony(changes=changes, duration_unit="bars")
        return self

    def progression(self, *chords: ChordArg) -> SectionBuilder:
        """Alias for harmony()."""
        return self.harmony(*chords)

    def track(
        self,
        name: str,
        role: Role = Role.HARMONY,
        instrument: str | int = "piano",
    ) -> TrackBuilder:
        """
        Create or access a track in this section.

        Args:
            name: Track identifier
            role: Musical role (MELODY, BASS, HARMONY, RHYTHM)
            instrument: MIDI instrument name or number
        """
        track = TrackBuilder(
            name=name,
            section=self,
            role=role,
            instrument=instrument,
        )
        self._tracks.append(track)
        return track

    def transform(
        self,
        name: str | None = None,
        reharmonize: str | None = None,
        transpose: int = 0,
        register: int = 0,
        include_content: bool = True,
    ) -> SectionBuilder:
        """
        Make a new section from this one.

        Tracks are copied and follow the new harmony by themselves, because they
        hold patterns and not notes.

        Args:
            name: Name of the new section (default "<name>_2")
            reharmonize: tritone_sub, jazzify, modal_interchange, secondary_dominants
            transpose: Semitones to move the section's key and literal notes
            register: Octaves to shift every pitched track
            include_content: If False, copy only the bars and meter

        Example:
            chorus = verse.transform("chorus", reharmonize="modal_interchange")
        """
        key = self._key or self._piece._key
        section = self._piece.section(
            name or f"{self._name}_2",
            bars=self._bars,
            key=transposed_key(key, transpose) if transpose else self._key,
            time_sig=self._time_signature,
        )
        if not include_content:
            return section
        changes = self._harmony.changes
        if reharmonize is not None:
            changes = reharmonize_changes(changes, key, reharmonize)
        section._harmony = Harmony(changes=list(changes), duration_unit=self._harmony.duration_unit)
        for track in self._tracks:
            copied = copy.copy(track)
            copied._section = section
            if track._role != Role.RHYTHM:
                copied._octave_shift = track._octave_shift + register
            if isinstance(track._content, Notes) and transpose and track._role != Role.RHYTHM:
                copied._content = Notes(
                    notes=[replace(n, pitch=n.pitch + transpose) if n.pitch >= 0 else n for n in track._content.notes]
                )
            section._tracks.append(copied)
        section._curves = list(self._curves)
        return section

    def automate(
        self, track: str, target: str, points: list[tuple[float | Fraction, float]]
    ) -> SectionBuilder:
        """
        Move a parameter during this section.

        Args:
            track: Track name
            target: "<device>.<parameter>", or "mix.volume" for the fader
            points: (bars from the section start, value 0..1) pairs. Values between
                points are interpolated by the DAW.

        Example:
            drop.automate("pad", "synth.A Filter 1 Cutoff", [(0, 0.3), (8, 0.8)])
        """
        meter = self._time_signature or self._piece._time_signature
        converted = [
            (
                Fraction(at).limit_denominator(3840) * meter.beats_per_bar,
                Fraction(value).limit_denominator(100000),
            )
            for at, value in points
        ]
        self._curves.append(Curve(track=track, target=target, points=converted))
        return self

    def _to_ir(self) -> Section:
        """Convert to IR Section object."""
        return Section(
            name=self._name,
            bars=self._bars,
            key=self._key,
            time_signature=self._time_signature,
            harmony=self._harmony,
            tracks=[t._to_ir() for t in self._tracks],
            curves=list(self._curves),
        )


# -----------------------------------------------------------------------------
# Piece Builder
# -----------------------------------------------------------------------------


class PieceBuilder:
    """
    Builder for creating pieces with method chaining.

    Usage:
        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=8)
            ...
        p.save_midi("output.mid")
    """

    def __init__(
        self,
        tempo: float = 120.0,
        key: str | Key = "C major",
        time_sig: str | TimeSignature = "4/4",
        title: str | None = None,
    ):
        self._tempo = tempo

        if isinstance(key, str):
            self._key = Key.parse(key)
        else:
            self._key = key

        if isinstance(time_sig, str):
            self._time_signature = TimeSignature.parse(time_sig)
        else:
            self._time_signature = time_sig

        self._title = title
        self._sections: list[SectionBuilder] = []
        self._form: list[str] | None = None
        self._racks: list[Rack] = []

    def section(
        self,
        name: str,
        bars: int,
        key: str | Key | None = None,
        time_sig: str | TimeSignature | None = None,
    ) -> SectionBuilder:
        """
        Create a section in this piece.

        Args:
            name: Section identifier (e.g., "verse", "chorus")
            bars: Length in bars
            key: Override key for this section (optional)
            time_sig: Override time signature (optional)
        """
        section_key = None
        if key is not None:
            section_key = Key.parse(key) if isinstance(key, str) else key

        section_time_sig = None
        if time_sig is not None:
            section_time_sig = (
                TimeSignature.parse(time_sig)
                if isinstance(time_sig, str)
                else time_sig
            )

        section = SectionBuilder(
            name=name,
            bars=bars,
            piece=self,
            key=section_key,
            time_signature=section_time_sig,
        )
        self._sections.append(section)
        return section

    def rack(
        self,
        track: str,
        *devices: Device,
        volume: float | None = None,
        pan: float | None = None,
        color: str | None = None,
        sends: dict[str, float] | None = None,
    ) -> PieceBuilder:
        """
        Say how a track sounds: its plugin chain, level, and routing.

        Args:
            track: Track name. It need not have notes, which is how a bus is declared.
            *devices: Plugins in chain order, the instrument first
            volume: Fader, normalised (0.74 is unity). None leaves it to the DAW.
            pan: -1 to 1. None leaves it to the DAW.
            color: A colour for the DAW to show the track in
            sends: Destination track name to linear gain

        Example:
            p.rack("pad", device("synth", SURGE_XT), sends={"verb": 0.4})
            p.rack("verb", device("reverb", "reverb"))
        """
        self._racks.append(
            Rack(
                track=track,
                devices=list(devices),
                volume=volume,
                pan=pan,
                color=color,
                sends=dict(sends or {}),
            )
        )
        return self

    def form(self, sections: list[SectionBuilder | str]) -> PieceBuilder:
        """
        Set the form (section order) for this piece.

        Args:
            sections: List of sections or section names in play order.
        """
        self._form = [
            s._name if isinstance(s, SectionBuilder) else s for s in sections
        ]
        return self

    def to_ir(self) -> Piece:
        """Convert to an IR Piece object."""
        return Piece(
            title=self._title,
            tempo=self._tempo,
            key=self._key,
            time_signature=self._time_signature,
            sections=[s._to_ir() for s in self._sections],
            form=self._form,
            racks=list(self._racks),
        )

    def to_midi(self, ticks_per_beat: int = 480) -> mido.MidiFile:
        """
        Convert to a mido MidiFile object.

        Args:
            ticks_per_beat: MIDI ticks per beat (default 480)

        Returns:
            mido.MidiFile object that can be played or further processed.
        """
        from pypulang.backends.midi import event_to_midi
        from pypulang.compiler import compile_piece

        module = compile_piece(self.to_ir(), until="event").stages["event"]
        return event_to_midi(module, ticks_per_beat=ticks_per_beat)

    def save_midi(self, path: str, ticks_per_beat: int = 480) -> None:
        """
        Save this piece to a MIDI file.

        Args:
            path: Output file path (e.g., "output.mid")
            ticks_per_beat: MIDI ticks per beat (default 480)
        """
        self.to_midi(ticks_per_beat=ticks_per_beat).save(path)

    def save_audio(
        self,
        path: str,
        instruments: InstrumentBank | None = None,
        sample_rate: int = 44100,
    ) -> None:
        """
        Render this piece and save to a WAV audio file.

        Uses the built-in synthesizer to render all tracks offline (no
        real-time playback) and writes the result to a .wav file via
        soundfile.

        Args:
            path: Output file path (e.g., "output.wav")
            instruments: Optional InstrumentBank for custom instrument sounds
            sample_rate: Audio sample rate in Hz (default 44100)

        Raises:
            RuntimeError: If numpy or soundfile is not installed

        Example:
            p.save_audio("output.wav")
            p.save_audio("output.wav", sample_rate=48000)
        """
        try:
            import soundfile as sf
        except ImportError as exc:
            raise RuntimeError(
                "soundfile is not installed. Install with: pip install pypulang[playback]"
            ) from exc

        from pypulang.playback.builtin_synth import BuiltinSynth

        synth = BuiltinSynth(sample_rate=sample_rate)
        from pypulang.compiler.pipeline import playback_events

        events, tempo = playback_events(self.to_ir())
        audio = synth.render_to_audio(events, tempo, instruments)

        # soundfile expects shape (samples,) for mono or (samples, channels) for stereo
        sf.write(path, audio, sample_rate)

    def save(self, path: str, **kwargs: Any) -> None:
        """
        Save this piece to a file, auto-detecting format from extension.

        Args:
            path: Output file path. Extension determines format:
                  - .mid, .midi → MIDI file
                  - .wav → WAV audio file
            **kwargs: Format-specific options (e.g., ticks_per_beat for MIDI,
                      sample_rate for WAV)
        """
        if path.endswith(".mid") or path.endswith(".midi"):
            self.save_midi(path, **kwargs)
        elif path.endswith(".wav"):
            self.save_audio(path, **kwargs)
        else:
            raise ValueError(
                f"Unknown file format: {path}. Supported: .mid, .midi, .wav"
            )

    # -------------------------------------------------------------------------
    # Playback Methods
    # -------------------------------------------------------------------------

    def play(
        self,
        backend: PlaybackBackend | None = None,
        instruments: InstrumentBank | None = None,
        from_bar: int | None = None,
        section: str | None = None,
        wait: bool = True,
    ) -> PlaybackHandle:
        """
        Play this piece.

        Args:
            backend: Playback backend to use (default: auto-detect)
            instruments: InstrumentBank for custom instrument sounds
            from_bar: Start from a specific bar (1-indexed)
            section: Play only a specific section
            wait: If True, block until playback completes

        Returns:
            PlaybackHandle for transport control

        Example:
            p.play()  # Play with defaults
            p.play(from_bar=5)  # Start from bar 5
            p.play(section="verse")  # Play only the verse

            # Custom instruments
            from pypulang.playback import Synth, InstrumentBank
            instruments = InstrumentBank({Role.BASS: Synth(waveform="saw")})
            p.play(instruments=instruments)
        """
        from pypulang.playback.config import get_default_backend

        if backend is None:
            backend = get_default_backend()

        # Realize piece to events
        ir = self.to_ir()
        from pypulang.compiler.pipeline import playback_events

        events, tempo = playback_events(ir, from_bar=from_bar, section=section)

        # Start playback
        handle = backend.play(events, tempo, instruments)

        if wait:
            handle.wait()

        return handle

    def loop(
        self,
        count: int | None = None,
        backend: PlaybackBackend | None = None,
        instruments: InstrumentBank | None = None,
        section: str | None = None,
        bars: int | None = None,
    ) -> PlaybackHandle:
        """
        Loop this piece or a section.

        Args:
            count: Number of loops (None = infinite until stopped)
            backend: Playback backend to use (default: auto-detect)
            instruments: InstrumentBank for custom instrument sounds
            section: Loop only a specific section
            bars: Loop only this many bars (from section start if section specified)

        Returns:
            PlaybackHandle for transport control (use .stop() to end loop)

        Example:
            handle = p.loop()  # Loop forever
            # ... later ...
            handle.stop()

            p.loop(count=4)  # Loop 4 times
            p.loop(section="verse")  # Loop the verse
        """
        from pypulang.playback.config import get_default_backend

        if backend is None:
            backend = get_default_backend()

        # Realize piece to events
        ir = self.to_ir()
        from pypulang.compiler.pipeline import playback_events

        events, tempo = playback_events(ir, section=section)

        # Handle bars limit - filter events to only those within bar range
        if bars is not None:
            beats_per_bar = float(self._time_signature.beats_per_bar)
            max_beat = bars * beats_per_bar
            events = [
                (pitch, start, dur, vel, track)
                for pitch, start, dur, vel, track in events
                if start < max_beat
            ]
            # Truncate notes that extend past the limit
            events = [
                (pitch, start, min(dur, max_beat - start), vel, track)
                for pitch, start, dur, vel, track in events
            ]

        # Create looping handle
        handle = _LoopingHandle(backend, events, tempo, instruments, count)
        handle._start()

        return handle

    def stop(self) -> None:
        """
        Stop any active playback for this piece.

        Note: This only works if you have a reference to the PlaybackHandle.
        Use the handle returned by play() or loop() for precise control.
        """
        # This is a convenience method but requires tracking active handles
        # For now, we recommend using the handle directly
        pass

    def connect(self, port: str = "pypulang") -> None:
        """
        Create a virtual MIDI port for DAW integration.

        Args:
            port: Name for the virtual MIDI port

        Example:
            p.connect(port="pypulang")
            p.play(backend=VirtualMidi("pypulang"))
        """
        from pypulang.playback import VirtualMidi

        midi_backend = VirtualMidi(port)
        if not midi_backend.connect():
            raise RuntimeError(f"Failed to create virtual MIDI port: {port}")

    def list_ports(self) -> list[str]:
        """
        List available MIDI output ports.

        Returns:
            List of port names
        """
        from pypulang.playback import VirtualMidi

        if VirtualMidi is None:
            return []
        midi_backend = VirtualMidi()
        return midi_backend.list_ports()

    def watch(
        self,
        source_file: str | None = None,
        backend: PlaybackBackend | None = None,
        instruments: InstrumentBank | None = None,
        loop: bool = True,
        from_bar: int | None = None,
        section: str | None = None,
    ) -> None:
        """
        Enable hot reload mode - watch source file and restart playback on save.

        This method blocks until interrupted (Ctrl+C). On each file save:
        1. Stops current playback
        2. Reloads the source module
        3. Restarts playback (best effort position preservation)

        Args:
            source_file: Path to watch (auto-detected from call stack if None)
            backend: Playback backend to use (default: auto-detect)
            instruments: InstrumentBank for custom instrument sounds
            loop: Whether to loop playback (default True for iteration)
            from_bar: Start from a specific bar
            section: Play only a specific section

        Example:
            from pypulang import piece, I, IV, vi, V, Role, root_quarters

            with piece(tempo=120, key="C major") as p:
                verse = p.section("verse", bars=4)
                verse.harmony(I, IV, vi, V)
                verse.track("bass", role=Role.BASS).pattern(root_quarters)

            # Watch for changes and auto-reload
            p.watch()  # Loops playback, reloads on save
        """
        from pypulang.playback.watcher import watch_piece

        handle = watch_piece(
            piece_builder=self,
            source_file=source_file,
            backend=backend,
            instruments=instruments,
            loop=loop,
            from_bar=from_bar,
            section=section,
        )

        # Block until interrupted
        try:
            while handle.is_watching():
                import time
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[watch] Stopping...")
            handle.stop()

    def __enter__(self) -> PieceBuilder:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        pass


class _LoopingHandle:
    """
    Handle for looping playback.

    Manages repeated playback until stopped or count is reached.
    """

    def __init__(
        self,
        backend: PlaybackBackend,
        events: list[tuple[int, float, float, int, str]],
        tempo: float,
        instruments: InstrumentBank | None,
        count: int | None,
    ) -> None:
        self._backend = backend
        self._events = events
        self._tempo = tempo
        self._instruments = instruments
        self._count = count
        self._current_handle: PlaybackHandle | None = None
        self._stopped = False
        self._loop_count = 0
        self._thread: Any = None

    def _start(self) -> None:
        """Start the looping playback."""
        import threading

        self._stopped = False
        self._loop_count = 0
        self._thread = threading.Thread(target=self._loop_thread, daemon=True)
        self._thread.start()

    def _loop_thread(self) -> None:
        """Thread that handles looping."""
        while not self._stopped:
            # Check count limit
            if self._count is not None and self._loop_count >= self._count:
                break

            # Start playback
            self._current_handle = self._backend.play(
                self._events, self._tempo, self._instruments
            )

            # Wait for this iteration to complete
            self._current_handle.wait()
            self._loop_count += 1

            if self._stopped:
                break

    def stop(self) -> None:
        """Stop looping playback."""
        self._stopped = True
        if self._current_handle is not None:
            self._current_handle.stop()

    def pause(self) -> None:
        """Pause current playback."""
        if self._current_handle is not None:
            self._current_handle.pause()

    def resume(self) -> None:
        """Resume paused playback."""
        if self._current_handle is not None:
            self._current_handle.resume()

    def is_playing(self) -> bool:
        """Check if currently playing."""
        if self._current_handle is not None:
            return self._current_handle.is_playing()
        return False

    def is_paused(self) -> bool:
        """Check if currently paused."""
        if self._current_handle is not None:
            return self._current_handle.is_paused()
        return False

    def wait(self) -> None:
        """Wait for looping to complete (only if count is set)."""
        if self._thread is not None:
            self._thread.join()


# -----------------------------------------------------------------------------
# piece() Function
# -----------------------------------------------------------------------------


def piece(
    tempo: float = 120.0,
    key: str | Key = "C major",
    time_sig: str | TimeSignature = "4/4",
    title: str | None = None,
) -> PieceBuilder:
    """
    Create a new piece.

    This is the main entry point for the pyPuLang DSL. Can be used as a
    context manager or standalone.

    Args:
        tempo: BPM (default 120)
        key: Key signature as string (e.g., "C major") or Key object
        time_sig: Time signature as string (e.g., "4/4") or TimeSignature object
        title: Optional piece title

    Returns:
        PieceBuilder that can be used to construct the piece.

    Example:
        with piece(tempo=100, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        p.save_midi("output.mid")
    """
    return PieceBuilder(tempo=tempo, key=key, time_sig=time_sig, title=title)
