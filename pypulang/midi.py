"""
MIDI emission for puLang.

This module converts Intent IR directly to MIDI files. In Phase 1, we skip
the Event IR layer and realize directly to MIDI for simplicity.

The main entry point is `realize_to_midi(piece: Piece) -> mido.MidiFile`.
"""

from __future__ import annotations

from fractions import Fraction

import mido

from pypulang.ir.intent import (
    Harmony,
    Key,
    Notes,
    Pattern,
    Piece,
    TimeSignature,
    Track,
)
from pypulang.patterns import generate_pattern
from pypulang.resolution import resolve_chord

# Standard MIDI ticks per quarter note (beat)
DEFAULT_TICKS_PER_BEAT = 480


def realize_to_midi(
    piece: Piece,
    ticks_per_beat: int = DEFAULT_TICKS_PER_BEAT,
) -> mido.MidiFile:
    """
    Convert a Piece (Intent IR) to a MIDI file.

    This walks through all sections, resolves chords, generates pattern notes,
    and creates a complete MIDI file with tempo and time signature.

    Args:
        piece: The Piece to realize
        ticks_per_beat: MIDI resolution (default 480)

    Returns:
        A mido.MidiFile object ready to be saved or played

    Example:
        >>> piece = Piece(tempo=120, key=Key("C", "major"))
        >>> # ... add sections and tracks ...
        >>> midi = realize_to_midi(piece)
        >>> midi.save("output.mid")
    """
    midi_file = mido.MidiFile(ticks_per_beat=ticks_per_beat)

    # Track 0: Tempo and time signature (conductor track)
    conductor_track = mido.MidiTrack()
    midi_file.tracks.append(conductor_track)

    # Set tempo (microseconds per beat)
    tempo_us = int(60_000_000 / piece.tempo)
    conductor_track.append(mido.MetaMessage("set_tempo", tempo=tempo_us, time=0))

    # Set time signature
    ts = piece.time_signature
    conductor_track.append(
        mido.MetaMessage(
            "time_signature",
            numerator=ts.numerator,
            denominator=ts.denominator,
            clocks_per_click=24,
            notated_32nd_notes_per_beat=8,
            time=0,
        )
    )

    # Add end of track
    conductor_track.append(mido.MetaMessage("end_of_track", time=0))

    # Collect all note events from all sections/tracks
    # Group by track name for MIDI track creation
    track_events: dict[str, list[tuple[int, Fraction, Fraction, int]]] = {}
    track_roles: dict[str, str | None] = {}  # Track name -> role

    # Process sections in form order (or linear if no form specified)
    section_order = piece.form if piece.form else [s.name for s in piece.sections]
    section_map = {s.name: s for s in piece.sections}

    current_beat = Fraction(0)

    for section_name in section_order:
        if section_name not in section_map:
            raise ValueError(f"Unknown section in form: {section_name}")

        section = section_map[section_name]

        # Resolve section-level key and time signature
        section_key = section.key if section.key else piece.key
        section_ts = section.time_signature if section.time_signature else piece.time_signature

        # Calculate section length in beats
        section_beats = Fraction(section.bars) * section_ts.beats_per_bar

        # Process each track in the section
        for track in section.tracks:
            if track.muted:
                continue

            if track.name not in track_events:
                track_events[track.name] = []
                track_roles[track.name] = track.role

            # Generate notes based on track content
            notes = _realize_track(
                track=track,
                harmony=section.harmony,
                key=section_key,
                time_signature=section_ts,
                section_offset=current_beat,
                section_bars=section.bars,
            )
            track_events[track.name].extend(notes)

        current_beat += section_beats

    # Create MIDI tracks for each puLang track
    for track_name, events in track_events.items():
        role = track_roles.get(track_name)
        midi_track = _create_midi_track(
            track_name=track_name,
            events=events,
            ticks_per_beat=ticks_per_beat,
            role=role,
        )
        midi_file.tracks.append(midi_track)

    return midi_file


def _realize_track(
    track: Track,
    harmony: Harmony,
    key: Key,
    time_signature: TimeSignature,
    section_offset: Fraction,
    section_bars: int,
) -> list[tuple[int, Fraction, Fraction, int]]:
    """
    Realize a track's content into note events.

    Returns:
        List of (pitch, start_beat, duration_beats, velocity) tuples
    """
    if track.content is None:
        return []

    events = []

    if isinstance(track.content, Pattern):
        events = _realize_pattern_track(
            track=track,
            harmony=harmony,
            key=key,
            time_signature=time_signature,
            section_offset=section_offset,
            section_bars=section_bars,
        )
    elif isinstance(track.content, Notes):
        events = _realize_notes_track(
            track=track,
            section_offset=section_offset,
        )

    return events


def _realize_pattern_track(
    track: Track,
    harmony: Harmony,
    key: Key,
    time_signature: TimeSignature,
    section_offset: Fraction,
    section_bars: int,
) -> list[tuple[int, Fraction, Fraction, int]]:
    """
    Realize a pattern-based track.

    Walks through the harmony changes, resolving chords and generating
    pattern notes for each chord's duration.
    """
    assert isinstance(track.content, Pattern)

    events = []
    pattern = track.content

    # Build track params for pattern generator
    track_params = {
        "octave_shift": track.octave_shift,
        "velocity": track.velocity,
    }

    # Calculate total section duration in beats
    section_beats = Fraction(section_bars) * time_signature.beats_per_bar

    # If no harmony changes, nothing to generate
    if not harmony.changes:
        return []

    # Calculate total harmony duration
    total_harmony_duration = harmony.total_duration()

    # Convert harmony duration to beats
    if harmony.duration_unit == "bars":
        harmony_beats = total_harmony_duration * time_signature.beats_per_bar
    else:  # "beats"
        harmony_beats = total_harmony_duration

    # Scale factor if harmony doesn't exactly match section length
    # (e.g., 4 chords for 8 bars means each chord gets 2 bars)
    if harmony_beats > 0 and section_beats > 0:
        scale_factor = section_beats / harmony_beats
    else:
        scale_factor = Fraction(1)

    # Walk through chord changes
    current_beat = Fraction(0)

    for change in harmony.changes:
        # Convert chord duration to beats
        if harmony.duration_unit == "bars":
            chord_beats = change.duration * time_signature.beats_per_bar * scale_factor
        else:
            chord_beats = change.duration * scale_factor

        # Resolve chord to pitches
        # Use octave 4 as base, track octave_shift will adjust
        chord_pitches = resolve_chord(change.chord, key, octave=4)

        # Generate pattern events for this chord
        pattern_events = generate_pattern(
            pattern_type=pattern.pattern_type,
            chord_pitches=chord_pitches,
            duration=chord_beats,
            offset=section_offset + current_beat,
            track_params=track_params,
            pattern_params=pattern.params,
        )

        events.extend(pattern_events)
        current_beat += chord_beats

    return events


def _realize_notes_track(
    track: Track,
    section_offset: Fraction,
) -> list[tuple[int, Fraction, Fraction, int]]:
    """
    Realize a literal notes track (escape hatch).
    """
    assert isinstance(track.content, Notes)

    events = []
    octave_shift = track.octave_shift
    default_velocity = track.velocity

    for note in track.content.notes:
        if note.pitch < 0:  # Rest
            continue

        pitch = note.pitch + (octave_shift * 12)
        start = section_offset + note.offset
        duration = note.duration
        velocity = note.velocity if note.velocity is not None else default_velocity

        events.append((pitch, start, duration, velocity))

    return events


def _create_midi_track(
    track_name: str,
    events: list[tuple[int, Fraction, Fraction, int]],
    ticks_per_beat: int,
    role: str | None = None,
) -> mido.MidiTrack:
    """
    Create a MIDI track from note events.

    MIDI uses delta times (time since last event), so we need to convert
    absolute beat positions to deltas and then to ticks.

    Args:
        track_name: Name of the track
        events: List of (pitch, start_beat, duration_beats, velocity) tuples
        ticks_per_beat: MIDI resolution
        role: Track role (used to determine MIDI channel; RHYTHM -> channel 10)

    Returns:
        A mido.MidiTrack ready to be added to a MIDI file
    """
    midi_track = mido.MidiTrack()

    # Track name
    midi_track.append(mido.MetaMessage("track_name", name=track_name, time=0))

    # Determine MIDI channel based on role
    # GM standard: channel 10 (0-indexed: 9) is for percussion/drums
    channel = 9 if role == "rhythm" else 0

    # Convert note events to MIDI messages
    # Each note needs a note_on and note_off event
    midi_events: list[tuple[int, str, int, int]] = []  # (tick, type, pitch, velocity)

    for pitch, start, duration, velocity in events:
        start_ticks = _beats_to_ticks(start, ticks_per_beat)
        end_ticks = _beats_to_ticks(start + duration, ticks_per_beat)

        # Clamp pitch to valid MIDI range
        pitch = max(0, min(127, pitch))
        velocity = max(0, min(127, velocity))

        midi_events.append((start_ticks, "note_on", pitch, velocity))
        midi_events.append((end_ticks, "note_off", pitch, 0))

    # Sort by time, with note_off before note_on at same time
    midi_events.sort(key=lambda e: (e[0], 0 if e[1] == "note_off" else 1))

    # Convert to delta times and add to track
    current_tick = 0
    for tick, msg_type, pitch, velocity in midi_events:
        delta = tick - current_tick
        current_tick = tick

        if msg_type == "note_on":
            midi_track.append(
                mido.Message("note_on", note=pitch, velocity=velocity, time=delta, channel=channel)
            )
        else:
            midi_track.append(
                mido.Message("note_off", note=pitch, velocity=velocity, time=delta, channel=channel)
            )

    # End of track
    midi_track.append(mido.MetaMessage("end_of_track", time=0))

    return midi_track


def _beats_to_ticks(beats: Fraction, ticks_per_beat: int) -> int:
    """
    Convert beat position (as Fraction) to MIDI ticks.

    Args:
        beats: Beat position as a Fraction
        ticks_per_beat: MIDI resolution

    Returns:
        Integer tick count
    """
    return int(beats * ticks_per_beat)


def save_midi(piece: Piece, path: str, ticks_per_beat: int = DEFAULT_TICKS_PER_BEAT) -> None:
    """
    Convenience function to realize and save a piece as MIDI.

    Args:
        piece: The Piece to save
        path: Output file path
        ticks_per_beat: MIDI resolution (default 480)
    """
    midi_file = realize_to_midi(piece, ticks_per_beat)
    midi_file.save(path)


def realize_to_events(
    piece: Piece,
    from_bar: int | None = None,
    section: str | None = None,
) -> tuple[list[tuple[int, float, float, int, str, str]], float]:
    """
    Realize a Piece to playback events.

    Returns events in a format suitable for playback backends:
    (pitch, start_beat, duration_beats, velocity, track_name, role)

    Args:
        piece: The Piece to realize
        from_bar: Optional starting bar number (1-indexed)
        section: Optional section name to realize only that section

    Returns:
        Tuple of (events list, tempo)
        Events are: (pitch, start_beat, duration_beats, velocity, track_name, role)
    """
    # Collect all note events with track names and roles
    all_events: list[tuple[int, float, float, int, str, str]] = []

    # Process sections in form order (or linear if no form specified)
    section_order = piece.form if piece.form else [s.name for s in piece.sections]
    section_map = {s.name: s for s in piece.sections}

    # Filter to specific section if requested
    if section is not None:
        if section not in section_map:
            raise ValueError(f"Unknown section: {section}")
        section_order = [section]

    current_beat = Fraction(0)
    start_beat_offset = Fraction(0)

    # Calculate start offset if from_bar is specified
    if from_bar is not None and from_bar > 1:
        bar_count = 0
        for section_name in section_order:
            sec = section_map[section_name]
            section_ts = sec.time_signature if sec.time_signature else piece.time_signature
            for _ in range(sec.bars):
                bar_count += 1
                if bar_count < from_bar:
                    start_beat_offset += section_ts.beats_per_bar

    for section_name in section_order:
        if section_name not in section_map:
            raise ValueError(f"Unknown section in form: {section_name}")

        sec = section_map[section_name]

        # Resolve section-level key and time signature
        section_key = sec.key if sec.key else piece.key
        section_ts = sec.time_signature if sec.time_signature else piece.time_signature

        # Calculate section length in beats
        section_beats = Fraction(sec.bars) * section_ts.beats_per_bar

        # Process each track in the section
        for track in sec.tracks:
            if track.muted:
                continue

            # Generate notes based on track content
            notes = _realize_track(
                track=track,
                harmony=sec.harmony,
                key=section_key,
                time_signature=section_ts,
                section_offset=current_beat,
                section_bars=sec.bars,
            )

            # Convert to playback event format with track name and role
            for pitch, start, duration, velocity in notes:
                # Adjust for from_bar offset
                adjusted_start = float(start - start_beat_offset)
                if adjusted_start >= 0:
                    all_events.append((
                        pitch,
                        adjusted_start,
                        float(duration),
                        velocity,
                        track.name,
                        track.role,
                    ))

        current_beat += section_beats

    return all_events, piece.tempo
