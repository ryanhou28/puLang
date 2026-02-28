"""
Full song demo - 16-bar piece with verse + chorus structure.

Demonstrates:
- Multiple tracks with different patterns
- Escape hatch for melody line (literal notes)
- Drum track with rock_beat pattern
- Verse/chorus structure
- Various pattern types (root_eighths, arp, block_chords, root_quarters)
"""

from pypulang import (
    I,
    IV,
    V,
    vi,
    Role,
    arp,
    block_chords,
    piece,
    rock_beat,
    root_eighths,
    root_quarters,
    four_on_floor,
)
from pypulang.pitches import D5, E5, Fs5, G5, A5, B5, rest


def main():
    """Compose a 16-bar piece with verse + chorus structure in G major."""

    with piece(tempo=120, key="G major", title="Full Song Demo") as p:
        # --- Verse: 8 bars (I - vi - IV - V, repeated) ---
        verse = p.section("verse", bars=8)
        verse.harmony(I, vi, IV, V)

        # Bass: root note eighth notes, two octaves down
        verse.track("bass", role=Role.BASS).pattern(root_eighths).octave(-2)

        # Keys: ascending arpeggio at sixteenth-note rate
        verse.track("keys", role=Role.HARMONY).pattern(arp("up"), rate=1 / 16)

        # Melody: literal notes using escape hatch
        verse.track("melody", role=Role.MELODY).notes([
            # Bar 1-2: Opening phrase (over I - vi)
            (D5, 1 / 4), (E5, 1 / 4), (G5, 1 / 2),
            (A5, 1 / 4), (G5, 1 / 4), (E5, 1 / 2),
            # Bar 3-4: Answering phrase (over IV - V)
            (B5, 1 / 4), (A5, 1 / 4), (G5, 1 / 4), (Fs5, 1 / 4),
            (E5, 1 / 4), (D5, 1 / 4), rest(1 / 2),
            # Bar 5-6: Second verse phrase (over I - vi)
            (G5, 1 / 4), (A5, 1 / 4), (B5, 1 / 2),
            (A5, 1 / 4), (G5, 1 / 4), (E5, 1 / 2),
            # Bar 7-8: Resolving phrase (over IV - V)
            (D5, 1 / 4), (E5, 1 / 4), (G5, 1 / 4), (A5, 1 / 4),
            (G5, 1),
        ])

        # Drums: rock beat throughout
        verse.track("drums", role=Role.RHYTHM).pattern(rock_beat)

        # --- Chorus: 8 bars (IV - V - I - vi, repeated) ---
        chorus = p.section("chorus", bars=8)
        chorus.harmony(IV, V, I, vi)

        # Bass: simpler root quarters, two octaves down
        chorus.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)

        # Keys: block chords at half-note rate for bigger sound
        chorus.track("keys", role=Role.HARMONY).pattern(block_chords, rate=1 / 2)

        # Melody: longer, more sustained notes for contrast
        chorus.track("melody", role=Role.MELODY).notes([
            # Bar 1-2: Bold opening (over IV - V)
            (B5, 1 / 2), (A5, 1 / 2),
            (G5, 1 / 2), (A5, 1 / 2),
            # Bar 3-4: Climax phrase (over I - vi)
            (B5, 1), (A5, 1 / 2), (G5, 1 / 2),
            # Bar 5-6: Echo of opening (over IV - V)
            (B5, 1 / 2), (A5, 1 / 2),
            (G5, 1 / 4), (A5, 1 / 4), (B5, 1 / 2),
            # Bar 7-8: Ending resolution (over I - vi)
            (A5, 1 / 4), (G5, 1 / 4), (E5, 1 / 4), (D5, 1 / 4),
            (G5, 1),
        ])

        # Drums: four on the floor for energy
        chorus.track("drums", role=Role.RHYTHM).pattern(four_on_floor)

    # Save to MIDI file
    p.save_midi("full_song.mid")
    print("Created full_song.mid (16 bars)")
    print("\nStructure:")
    print("  Bars 1-8:  Verse  (G major: I-vi-IV-V)")
    print("  Bars 9-16: Chorus (G major: IV-V-I-vi)")
    print("\nTracks:")
    print("  - Bass:   root_eighths (verse) / root_quarters (chorus)")
    print("  - Keys:   arp up 1/16 (verse) / block_chords 1/2 (chorus)")
    print("  - Melody: literal notes (escape hatch)")
    print("  - Drums:  rock_beat (verse) / four_on_floor (chorus)")

    # Also verify we can get the IR and MIDI objects
    ir = p.to_ir()
    print(f"\nIR: {len(ir.sections)} sections, "
          f"{sum(len(s.tracks) for s in ir.sections)} total tracks")

    midi = p.to_midi()
    print(f"MIDI: {len(midi.tracks)} tracks, "
          f"{midi.ticks_per_beat} ticks/beat")


if __name__ == "__main__":
    main()
