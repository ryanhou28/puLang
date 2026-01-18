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

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import TYPE_CHECKING, Any, Iterator, Union

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
    TrackContent,
)
from pypulang.midi import realize_to_midi, realize_to_events, save_midi

if TYPE_CHECKING:
    import mido
    from pypulang.playback.protocols import PlaybackBackend, PlaybackHandle
    from pypulang.playback.instruments import InstrumentBank


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


# -----------------------------------------------------------------------------
# Track Builder
# -----------------------------------------------------------------------------


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
                ir_notes.append(Note(
                    pitch=item.pitch,
                    duration=item.duration,
                    velocity=item.velocity,
                    offset=current_offset,
                ))
                current_offset += item.duration

            elif isinstance(item, ChordSpec):
                # ChordSpec from chord() - multiple simultaneous notes
                for pitch in item.pitches:
                    ir_notes.append(Note(
                        pitch=pitch,
                        duration=item.duration,
                        velocity=item.velocity,
                        offset=current_offset,
                    ))
                current_offset += item.duration

            elif isinstance(item, tuple):
                # Tuple syntax: (pitch, duration) or (pitch, duration, velocity)
                if len(item) == 2:
                    pitch, duration = item
                    velocity = None
                elif len(item) == 3:
                    pitch, duration, velocity = item
                else:
                    raise ValueError(f"Invalid note tuple: {item}. Expected 2 or 3 elements.")

                ir_notes.append(Note(
                    pitch=int(pitch),
                    duration=Fraction(duration) if not isinstance(duration, Fraction) else duration,
                    velocity=velocity,
                    offset=current_offset,
                ))
                current_offset += Fraction(duration) if not isinstance(duration, Fraction) else duration

            else:
                raise TypeError(
                    f"Invalid note type: {type(item)}. "
                    "Expected tuple, NoteSpec, or ChordSpec."
                )

        self._content = Notes(notes=ir_notes)
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

    def _to_ir(self) -> Track:
        """Convert to IR Track object."""
        return Track(
            name=self._name,
            role=self._role.value,
            instrument=self._instrument,
            content=self._content,
            octave_shift=self._octave_shift,
            velocity=self._velocity,
            muted=self._muted,
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

    def _to_ir(self) -> Section:
        """Convert to IR Section object."""
        return Section(
            name=self._name,
            bars=self._bars,
            key=self._key,
            time_signature=self._time_signature,
            harmony=self._harmony,
            tracks=[t._to_ir() for t in self._tracks],
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
        )

    def to_midi(self, ticks_per_beat: int = 480) -> "mido.MidiFile":
        """
        Convert to a mido MidiFile object.

        Args:
            ticks_per_beat: MIDI ticks per beat (default 480)

        Returns:
            mido.MidiFile object that can be played or further processed.
        """
        ir = self.to_ir()
        return realize_to_midi(ir, ticks_per_beat=ticks_per_beat)

    def save_midi(self, path: str, ticks_per_beat: int = 480) -> None:
        """
        Save this piece to a MIDI file.

        Args:
            path: Output file path (e.g., "output.mid")
            ticks_per_beat: MIDI ticks per beat (default 480)
        """
        ir = self.to_ir()
        save_midi(ir, path, ticks_per_beat=ticks_per_beat)

    def save(self, path: str, **kwargs: Any) -> None:
        """
        Save this piece to a file, auto-detecting format from extension.

        Args:
            path: Output file path. Extension determines format:
                  - .mid, .midi → MIDI file
                  - .xml (future) → MusicXML file
            **kwargs: Format-specific options (e.g., ticks_per_beat for MIDI)
        """
        if path.endswith(".mid") or path.endswith(".midi"):
            self.save_midi(path, **kwargs)
        else:
            raise ValueError(
                f"Unknown file format: {path}. Supported: .mid, .midi"
            )

    # -------------------------------------------------------------------------
    # Playback Methods
    # -------------------------------------------------------------------------

    def play(
        self,
        backend: "PlaybackBackend | None" = None,
        instruments: "InstrumentBank | None" = None,
        from_bar: int | None = None,
        section: str | None = None,
        wait: bool = True,
    ) -> "PlaybackHandle":
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
        events, tempo = realize_to_events(ir, from_bar=from_bar, section=section)

        # Start playback
        handle = backend.play(events, tempo, instruments)

        if wait:
            handle.wait()

        return handle

    def loop(
        self,
        count: int | None = None,
        backend: "PlaybackBackend | None" = None,
        instruments: "InstrumentBank | None" = None,
        section: str | None = None,
        bars: int | None = None,
    ) -> "PlaybackHandle":
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
        events, tempo = realize_to_events(ir, section=section)

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
        backend: "PlaybackBackend | None" = None,
        instruments: "InstrumentBank | None" = None,
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
        backend: "PlaybackBackend",
        events: list[tuple[int, float, float, int, str]],
        tempo: float,
        instruments: "InstrumentBank | None",
        count: int | None,
    ) -> None:
        self._backend = backend
        self._events = events
        self._tempo = tempo
        self._instruments = instruments
        self._count = count
        self._current_handle: "PlaybackHandle | None" = None
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
