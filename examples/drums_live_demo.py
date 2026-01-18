"""
Live drums demo - Phase 2.5

Interactive demo with live audio playback of drum patterns.
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


def demo_rock_beat():
    """Demo 1: Classic rock beat with bass."""
    print("\n=== Demo 1: Rock Beat ===")
    print("Classic rock: kick on 1&3, snare on 2&4, eighth-note hats")

    with piece(tempo=120, key="C major") as p:
        verse = p.section("verse", bars=4)
        verse.harmony(I, IV, vi, V)
        verse.track("drums", role=Role.RHYTHM).pattern(rock_beat)
        verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

    print("Playing... (press Ctrl+C to stop)")
    p.play()


def demo_four_on_floor():
    """Demo 2: Dance/electronic beat."""
    print("\n=== Demo 2: Four-on-the-Floor ===")
    print("Dance beat: kick on every beat")

    with piece(tempo=128, key="G major") as p:
        chorus = p.section("chorus", bars=4)
        chorus.harmony(vi, IV, I, V)
        chorus.track("drums", role=Role.RHYTHM).pattern(four_on_floor)
        chorus.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)
        chorus.track("chords", role=Role.HARMONY).pattern(block_chords)

    print("Playing... (press Ctrl+C to stop)")
    p.play()


def demo_shuffle():
    """Demo 3: Shuffle/swing groove."""
    print("\n=== Demo 3: Shuffle ===")
    print("Swing feel with triplet hi-hats")

    with piece(tempo=110, key="D major") as p:
        bridge = p.section("bridge", bars=4)
        bridge.harmony(I, IV, I, V)
        bridge.track("drums", role=Role.RHYTHM).pattern(shuffle)
        bridge.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

    print("Playing... (press Ctrl+C to stop)")
    p.play()


def demo_layered_drums():
    """Demo 4: Layered drums (backbeat + hi-hats)."""
    print("\n=== Demo 4: Layered Drums ===")
    print("Separate tracks for backbeat and hi-hats")

    with piece(tempo=100, key="A minor") as p:
        breakdown = p.section("breakdown", bars=4)
        breakdown.harmony(i, i, i, i)
        breakdown.track("snare", role=Role.RHYTHM).pattern(backbeat)
        breakdown.track("hats", role=Role.RHYTHM).pattern(eighth_hats)

    print("Playing... (press Ctrl+C to stop)")
    p.play()


def demo_literal_drums():
    """Demo 5: Literal drum notation with special sounds."""
    print("\n=== Demo 5: Literal Drum Notation ===")
    print("Custom drum pattern with cowbell and crash")

    from pypulang.drums import CLAP, COWBELL, CRASH, HIHAT_CLOSED, KICK, SNARE

    with piece(tempo=115, key="E major") as p:
        outro = p.section("outro", bars=4)
        outro.harmony(I, IV, I, V)
        outro.track("percussion", role=Role.RHYTHM).notes([
            # Bar 1: Kick and clap
            (KICK, 1/4), (CLAP, 1/4), (KICK, 1/4), (CLAP, 1/4),
            # Bar 2: Add cowbell
            (KICK, 1/4), (COWBELL, 1/8), (COWBELL, 1/8),
            (SNARE, 1/4), (COWBELL, 1/4),
            # Bar 3: Hi-hats
            (KICK, 1/8), (HIHAT_CLOSED, 1/8), (HIHAT_CLOSED, 1/8), (HIHAT_CLOSED, 1/8),
            (KICK, 1/8), (HIHAT_CLOSED, 1/8), (HIHAT_CLOSED, 1/8), (HIHAT_CLOSED, 1/8),
            # Bar 4: Crash ending
            (KICK, 1/4), (SNARE, 1/4), (KICK, 1/4), (CRASH, 1),
        ])

    print("Playing... (press Ctrl+C to stop)")
    p.play()


def demo_all_patterns():
    """Demo 6: All patterns in sequence."""
    print("\n=== Demo 6: All Patterns Showcase ===")
    print("Cycling through all drum patterns")

    with piece(tempo=120, key="C major") as p:
        # Rock beat
        verse1 = p.section("verse1", bars=4)
        verse1.harmony(I, IV, vi, V)
        verse1.track("drums", role=Role.RHYTHM).pattern(rock_beat)
        verse1.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        # Four-on-the-floor
        chorus = p.section("chorus", bars=4)
        chorus.harmony(vi, IV, I, V)
        chorus.track("drums", role=Role.RHYTHM).pattern(four_on_floor)
        chorus.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        # Shuffle
        bridge = p.section("bridge", bars=4)
        bridge.harmony(IV, V, I, I)
        bridge.track("drums", role=Role.RHYTHM).pattern(shuffle)
        bridge.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

        # Layered
        breakdown = p.section("breakdown", bars=4)
        breakdown.harmony(I, I, I, I)
        breakdown.track("snare", role=Role.RHYTHM).pattern(backbeat)
        breakdown.track("hats", role=Role.RHYTHM).pattern(eighth_hats)

    print("Playing full showcase... (press Ctrl+C to stop)")
    p.play()


def main():
    """Interactive menu."""
    print("=" * 60)
    print("Phase 2.5 - Live Drums Demo")
    print("=" * 60)
    print("\nSelect a demo to play:")
    print("  1. Rock Beat (classic)")
    print("  2. Four-on-the-Floor (dance)")
    print("  3. Shuffle (swing)")
    print("  4. Layered Drums (backbeat + hats)")
    print("  5. Literal Notation (custom pattern)")
    print("  6. All Patterns Showcase")
    print("  0. Exit")

    while True:
        try:
            choice = input("\nEnter choice (0-6): ").strip()

            if choice == "0":
                print("Goodbye!")
                break
            elif choice == "1":
                demo_rock_beat()
            elif choice == "2":
                demo_four_on_floor()
            elif choice == "3":
                demo_shuffle()
            elif choice == "4":
                demo_layered_drums()
            elif choice == "5":
                demo_literal_drums()
            elif choice == "6":
                demo_all_patterns()
            else:
                print("Invalid choice. Please enter 0-6.")
        except KeyboardInterrupt:
            print("\n\nStopped playback.")
        except EOFError:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
