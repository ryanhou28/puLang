"""
Pattern generators for puLang.

This module provides pattern generators that convert chord/harmony context
into concrete note events. Patterns are the core abstraction for generating
accompaniment, bass lines, arpeggios, etc.

Pattern Signature:
    (chord_pitches: list[int], duration: Fraction, offset: Fraction,
     track_params: dict, pattern_params: dict) -> list[tuple]

Returns:
    List of (pitch: int, start: Fraction, duration: Fraction, velocity: int) tuples
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Callable

# Type alias for note events
# (pitch, start_offset, duration, velocity)
NoteEvent = tuple[int, Fraction, Fraction, int]

# Type alias for pattern generator functions
PatternGenerator = Callable[
    [list[int], Fraction, Fraction, dict[str, Any], dict[str, Any]], list[NoteEvent]
]

# The pattern registry - maps pattern names to generator functions
PATTERN_REGISTRY: dict[str, PatternGenerator] = {}


def register_pattern(name: str):
    """
    Decorator to register a pattern generator.

    Usage:
        @register_pattern("my_pattern")
        def my_pattern_generator(chord_pitches, duration, offset, track_params, pattern_params):
            ...
    """

    def decorator(func: PatternGenerator) -> PatternGenerator:
        PATTERN_REGISTRY[name] = func
        return func

    return decorator


def get_pattern(name: str) -> PatternGenerator:
    """
    Get a pattern generator by name.

    Args:
        name: Pattern name (e.g., "root_quarters")

    Returns:
        Pattern generator function

    Raises:
        KeyError: If pattern is not registered
    """
    if name not in PATTERN_REGISTRY:
        raise KeyError(f"Unknown pattern: {name}. Available: {list(PATTERN_REGISTRY.keys())}")
    return PATTERN_REGISTRY[name]


def generate_pattern(
    pattern_type: str,
    chord_pitches: list[int],
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],
) -> list[NoteEvent]:
    """
    Generate notes using a named pattern.

    This is the main entry point for pattern generation.

    Args:
        pattern_type: Name of the pattern to use
        chord_pitches: MIDI pitches of the current chord (sorted low to high)
        duration: Duration of this chord in beats
        offset: Start offset of this chord in beats (from section start)
        track_params: Parameters from the track (octave_shift, velocity, etc.)
        pattern_params: Pattern-specific parameters

    Returns:
        List of (pitch, start, duration, velocity) tuples
    """
    generator = get_pattern(pattern_type)
    return generator(chord_pitches, duration, offset, track_params, pattern_params)


# -----------------------------------------------------------------------------
# Built-in Patterns
# -----------------------------------------------------------------------------


@register_pattern("root_quarters")
def root_quarters(
    chord_pitches: list[int],
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],
) -> list[NoteEvent]:
    """
    Play the root note of the chord on each quarter note beat.

    This is the simplest bass pattern - just play the root on each beat.

    Args:
        chord_pitches: MIDI pitches (lowest is typically the root or bass note)
        duration: Duration of this chord in beats
        offset: Start offset in beats
        track_params: Track parameters (octave_shift, velocity)
        pattern_params: Pattern-specific params (unused for root_quarters)

    Returns:
        List of quarter-note root notes
    """
    # Get the bass/root note (lowest pitch)
    root = chord_pitches[0]

    # Apply octave shift from track
    octave_shift = track_params.get("octave_shift", 0)
    root = root + (octave_shift * 12)

    # Get velocity from track (default 100)
    velocity = track_params.get("velocity", 100)

    # Generate quarter notes for the duration
    note_duration = Fraction(1)  # Quarter note = 1 beat
    events = []

    current_beat = Fraction(0)
    while current_beat < duration:
        # Calculate actual note duration (may be shorter at end)
        actual_duration = min(note_duration, duration - current_beat)

        events.append(
            (
                root,
                offset + current_beat,
                actual_duration,
                velocity,
            )
        )
        current_beat += note_duration

    return events


@register_pattern("root_eighths")
def root_eighths(
    chord_pitches: list[int],
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],
) -> list[NoteEvent]:
    """
    Play the root note of the chord on each eighth note.

    Similar to root_quarters but at double speed.
    """
    root = chord_pitches[0]
    octave_shift = track_params.get("octave_shift", 0)
    root = root + (octave_shift * 12)
    velocity = track_params.get("velocity", 100)

    note_duration = Fraction(1, 2)  # Eighth note = 1/2 beat
    events = []

    current_beat = Fraction(0)
    while current_beat < duration:
        actual_duration = min(note_duration, duration - current_beat)
        events.append(
            (
                root,
                offset + current_beat,
                actual_duration,
                velocity,
            )
        )
        current_beat += note_duration

    return events


@register_pattern("root_fifths")
def root_fifths(
    chord_pitches: list[int],
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],
) -> list[NoteEvent]:
    """
    Alternate between root and fifth on each beat.

    Classic bass pattern: root on beat 1 and 3, fifth on beat 2 and 4.
    """
    root = chord_pitches[0]
    # Find the fifth (7 semitones above root, or use chord's fifth if present)
    fifth = root + 7  # Perfect fifth
    if len(chord_pitches) >= 3:
        # Third element is typically the fifth in a triad
        fifth = chord_pitches[2]

    octave_shift = track_params.get("octave_shift", 0)
    root = root + (octave_shift * 12)
    fifth = fifth + (octave_shift * 12)

    velocity = track_params.get("velocity", 100)
    note_duration = Fraction(1)
    events = []

    current_beat = Fraction(0)
    use_root = True

    while current_beat < duration:
        pitch = root if use_root else fifth
        actual_duration = min(note_duration, duration - current_beat)

        events.append(
            (
                pitch,
                offset + current_beat,
                actual_duration,
                velocity,
            )
        )

        current_beat += note_duration
        use_root = not use_root

    return events


@register_pattern("block_chords")
def block_chords(
    chord_pitches: list[int],
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],
) -> list[NoteEvent]:
    """
    Play all chord tones simultaneously at a specified rate.

    Args:
        pattern_params:
            rate: Note value for hits (default 1 = quarter notes)
    """
    octave_shift = track_params.get("octave_shift", 0)
    velocity = track_params.get("velocity", 100)

    # Get rate from pattern params (default to quarter notes)
    rate = pattern_params.get("rate", 1)
    if isinstance(rate, str):
        rate = Fraction(rate)
    elif not isinstance(rate, Fraction):
        rate = Fraction(rate)

    note_duration = rate
    events = []

    current_beat = Fraction(0)
    while current_beat < duration:
        actual_duration = min(note_duration, duration - current_beat)

        # Add all chord tones
        for pitch in chord_pitches:
            shifted_pitch = pitch + (octave_shift * 12)
            events.append(
                (
                    shifted_pitch,
                    offset + current_beat,
                    actual_duration,
                    velocity,
                )
            )

        current_beat += note_duration

    return events


@register_pattern("arp")
def arp(
    chord_pitches: list[int],
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],
) -> list[NoteEvent]:
    """
    Arpeggiate chord tones.

    Args:
        pattern_params:
            direction: "up", "down", "updown" (default "up")
            rate: Note value (default 1/8 = eighth notes)
    """
    octave_shift = track_params.get("octave_shift", 0)
    velocity = track_params.get("velocity", 100)

    direction = pattern_params.get("direction", "up")
    rate = pattern_params.get("rate", Fraction(1, 8))
    if isinstance(rate, str):
        rate = Fraction(rate)
    elif not isinstance(rate, Fraction):
        rate = Fraction(rate)

    # Build the pitch sequence based on direction
    if direction == "up":
        sequence = chord_pitches
    elif direction == "down":
        sequence = list(reversed(chord_pitches))
    elif direction == "updown":
        # Up then down (excluding repeated top note)
        sequence = chord_pitches + list(reversed(chord_pitches[:-1]))
    else:
        sequence = chord_pitches  # Default to up

    if not sequence:
        return []

    events = []
    current_beat = Fraction(0)
    seq_index = 0

    while current_beat < duration:
        pitch = sequence[seq_index % len(sequence)]
        shifted_pitch = pitch + (octave_shift * 12)
        actual_duration = min(rate, duration - current_beat)

        events.append(
            (
                shifted_pitch,
                offset + current_beat,
                actual_duration,
                velocity,
            )
        )

        current_beat += rate
        seq_index += 1

    return events


# -----------------------------------------------------------------------------
# Drum Patterns
# -----------------------------------------------------------------------------
# Drum patterns ignore chord_pitches since they use fixed drum sounds.
# These patterns use GM drum map constants from the drums module.


@register_pattern("rock_beat")
def rock_beat(
    chord_pitches: list[int],  # noqa: ARG001 - drums ignore chord context
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],
) -> list[NoteEvent]:
    """
    Classic rock drum beat.

    Pattern (in 4/4):
    - Kick: beats 1 and 3
    - Snare: beats 2 and 4
    - Hi-hat: eighth notes (all beats)

    Args:
        pattern_params:
            hihat: "closed" (default) or "open"
            tempo_feel: "straight" (default) or "swing" (for future use)
    """
    # Lazy import to avoid circular dependency
    from pypulang import drums

    velocity = track_params.get("velocity", 100)
    hihat_type = pattern_params.get("hihat", "closed")

    # Choose hihat sound
    hihat = drums.HIHAT_CLOSED if hihat_type == "closed" else drums.HIHAT_OPEN

    events = []
    current_beat = Fraction(0)

    while current_beat < duration:
        beat_in_bar = current_beat % 4

        # Kick on beats 1 and 3 (0-indexed: 0 and 2)
        if beat_in_bar == 0 or beat_in_bar == 2:
            events.append((drums.KICK.midi, offset + current_beat, Fraction(1, 4), velocity))

        # Snare on beats 2 and 4 (0-indexed: 1 and 3)
        if beat_in_bar == 1 or beat_in_bar == 3:
            events.append((drums.SNARE.midi, offset + current_beat, Fraction(1, 4), velocity))

        # Hi-hat on every eighth note
        for eighth in [Fraction(0), Fraction(1, 2)]:
            if current_beat + eighth < duration:
                # Slightly lower velocity for hi-hat
                hihat_vel = int(velocity * 0.7)
                events.append((hihat.midi, offset + current_beat + eighth, Fraction(1, 8), hihat_vel))

        current_beat += 1  # Move to next beat

    return events


@register_pattern("four_on_floor")
def four_on_floor(
    chord_pitches: list[int],  # noqa: ARG001 - drums ignore chord context
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],
) -> list[NoteEvent]:
    """
    Four-on-the-floor dance beat.

    Pattern:
    - Kick: every beat (1, 2, 3, 4)
    - Hi-hat: eighth notes or sixteenth notes

    Args:
        pattern_params:
            hihat_rate: 1/8 (default) or 1/16
    """
    # Lazy import to avoid circular dependency
    from pypulang import drums

    velocity = track_params.get("velocity", 100)
    hihat_rate = pattern_params.get("hihat_rate", Fraction(1, 8))
    if not isinstance(hihat_rate, Fraction):
        hihat_rate = Fraction(hihat_rate)

    events = []
    current_beat = Fraction(0)

    # Kick on every beat
    while current_beat < duration:
        events.append((drums.KICK.midi, offset + current_beat, Fraction(1, 4), velocity))
        current_beat += 1

    # Hi-hat at specified rate
    current_time = Fraction(0)
    hihat_vel = int(velocity * 0.6)
    while current_time < duration:
        events.append((drums.HIHAT_CLOSED.midi, offset + current_time, hihat_rate, hihat_vel))
        current_time += hihat_rate

    return events


@register_pattern("backbeat")
def backbeat(
    chord_pitches: list[int],  # noqa: ARG001 - drums ignore chord context
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],  # noqa: ARG001 - no params for backbeat
) -> list[NoteEvent]:
    """
    Simple backbeat pattern - snare on beats 2 and 4 only.

    Useful for layering with other drum patterns or creating minimal grooves.
    """
    # Lazy import to avoid circular dependency
    from pypulang import drums

    velocity = track_params.get("velocity", 100)
    events = []

    current_beat = Fraction(0)
    while current_beat < duration:
        beat_in_bar = current_beat % 4

        # Snare on beats 2 and 4 (0-indexed: 1 and 3)
        if beat_in_bar == 1 or beat_in_bar == 3:
            events.append((drums.SNARE.midi, offset + current_beat, Fraction(1, 4), velocity))

        current_beat += 1

    return events


@register_pattern("eighth_hats")
def eighth_hats(
    chord_pitches: list[int],  # noqa: ARG001 - drums ignore chord context
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],
) -> list[NoteEvent]:
    """
    Hi-hat pattern - eighth notes only.

    Useful for layering with other drum patterns or creating minimal hi-hat grooves.

    Args:
        pattern_params:
            hihat: "closed" (default) or "open"
    """
    # Lazy import to avoid circular dependency
    from pypulang import drums

    velocity = track_params.get("velocity", 100)
    hihat_type = pattern_params.get("hihat", "closed")

    hihat = drums.HIHAT_CLOSED if hihat_type == "closed" else drums.HIHAT_OPEN

    events = []
    current_time = Fraction(0)
    rate = Fraction(1, 2)  # Eighth notes

    while current_time < duration:
        events.append((hihat.midi, offset + current_time, rate, velocity))
        current_time += rate

    return events


@register_pattern("shuffle")
def shuffle(
    chord_pitches: list[int],  # noqa: ARG001 - drums ignore chord context
    duration: Fraction,
    offset: Fraction,
    track_params: dict[str, Any],
    pattern_params: dict[str, Any],
) -> list[NoteEvent]:
    """
    Shuffle/swing drum pattern.

    Pattern:
    - Kick on beats 1 and 3
    - Snare on beats 2 and 4
    - Swung hi-hat (triplet feel)

    Args:
        pattern_params:
            swing_ratio: 2.0 (default, 2:1 triplet swing) or custom ratio (unused for now)
    """
    # Lazy import to avoid circular dependency
    from pypulang import drums

    velocity = track_params.get("velocity", 100)
    _ = pattern_params.get("swing_ratio", 2.0)  # Reserved for future use

    events = []
    current_beat = Fraction(0)

    while current_beat < duration:
        beat_in_bar = current_beat % 4

        # Kick on beats 1 and 3
        if beat_in_bar == 0 or beat_in_bar == 2:
            events.append((drums.KICK.midi, offset + current_beat, Fraction(1, 4), velocity))

        # Snare on beats 2 and 4
        if beat_in_bar == 1 or beat_in_bar == 3:
            events.append((drums.SNARE.midi, offset + current_beat, Fraction(1, 4), velocity))

        # Swung hi-hat (triplet-based)
        # In shuffle, we divide each beat into triplets: first and third triplet get hits
        triplet_duration = Fraction(1, 3)
        hihat_vel = int(velocity * 0.7)

        # First triplet (on the beat)
        if current_beat < duration:
            events.append(
                (drums.HIHAT_CLOSED.midi, offset + current_beat, triplet_duration, hihat_vel)
            )

        # Third triplet (swung eighth note)
        swung_offset = current_beat + (triplet_duration * 2)
        if swung_offset < duration:
            events.append(
                (drums.HIHAT_CLOSED.midi, offset + swung_offset, triplet_duration, hihat_vel)
            )

        current_beat += 1

    return events
