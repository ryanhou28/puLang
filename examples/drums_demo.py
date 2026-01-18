"""
Drums demo - Phase 2.5

Demonstrates drum patterns and literal drum notation.
"""

from pypulang import (
    I,
    IV,
    V,
    vi,
    Role,
    backbeat,
    block_chords,
    eighth_hats,
    four_on_floor,
    piece,
    rock_beat,
    root_quarters,
    shuffle,
)
from pypulang.drums import CLAP, COWBELL, CRASH, HIHAT_CLOSED, KICK, SNARE
from pypulang.pitches import note, rest


def main():
    """Create a multi-section piece demonstrating all drum patterns."""

    with piece(tempo=120, key="C major") as p:
        # Section 1: Rock beat with bass and chords
        verse = p.section("verse", bars=8)
        verse.harmony(I, IV, vi, V)
        verse.track("drums", role=Role.RHYTHM).pattern(rock_beat)
        verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)
        verse.track("chords", role=Role.HARMONY).pattern(block_chords)

        # Section 2: Four-on-the-floor dance beat
        chorus = p.section("chorus", bars=8)
        chorus.harmony(vi, IV, I, V)
        chorus.track("drums", role=Role.RHYTHM).pattern(four_on_floor)
        chorus.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        # Section 3: Shuffle/swing groove
        bridge = p.section("bridge", bars=4)
        bridge.harmony(IV, V, I, I)
        bridge.track("drums", role=Role.RHYTHM).pattern(shuffle)
        bridge.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        # Section 4: Layered drums using multiple patterns
        breakdown = p.section("breakdown", bars=4)
        breakdown.harmony(I, I, I, I)  # Static harmony
        # Just backbeat
        breakdown.track("snare", role=Role.RHYTHM).pattern(backbeat)
        # Just hi-hats
        breakdown.track("hats", role=Role.RHYTHM).pattern(eighth_hats)

        # Section 5: Literal drum notation with special sounds
        outro = p.section("outro", bars=4)
        outro.harmony(I, IV, I, V)
        outro.track("percussion", role=Role.RHYTHM).notes(
            [
                # Bar 1: Kick and clap pattern
                (KICK, 1 / 4),
                (CLAP, 1 / 4),
                (KICK, 1 / 4),
                (CLAP, 1 / 4),
                # Bar 2: Hi-hats with kick
                (KICK, 1 / 8),
                (HIHAT_CLOSED, 1 / 8),
                (HIHAT_CLOSED, 1 / 8),
                (HIHAT_CLOSED, 1 / 8),
                (KICK, 1 / 8),
                (HIHAT_CLOSED, 1 / 8),
                (HIHAT_CLOSED, 1 / 8),
                (HIHAT_CLOSED, 1 / 8),
                # Bar 3: Add cowbell
                (KICK, 1 / 4),
                (COWBELL, 1 / 8),
                (COWBELL, 1 / 8),
                (SNARE, 1 / 4),
                (COWBELL, 1 / 4),
                # Bar 4: Crash ending
                (KICK, 1 / 4),
                (SNARE, 1 / 4),
                (KICK, 1 / 4),
                (CRASH, 1),  # Crash cymbal on final beat (whole note)
            ]
        )

    # Save to MIDI file
    p.save_midi("drums_demo.mid")
    print("Created drums_demo.mid")
    print("\nDrum sections:")
    print("  - Verse: Classic rock beat (kick on 1&3, snare on 2&4, eighth note hats)")
    print("  - Chorus: Four-on-the-floor (kick on every beat)")
    print("  - Bridge: Shuffle/swing pattern (triplet feel)")
    print("  - Breakdown: Layered backbeat + hi-hats")
    print("  - Outro: Literal notation with special percussion sounds")
    print(
        "\nNote: Drum tracks automatically use MIDI channel 10 (GM percussion standard)"
    )


if __name__ == "__main__":
    main()
