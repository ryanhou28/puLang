"""
pyPuLang hot reload example - Live coding with instant feedback.

This example demonstrates the hot reload system:

1. Start this file with `python examples/hot_reload.py`
2. The music will start playing in a loop
3. Edit this file and save - playback will restart with your changes!
4. Press Ctrl+C to stop

Try changing:
- The tempo (e.g., 120 -> 140)
- The key (e.g., "C major" -> "G major")
- The chord progression
- Add more tracks
- Change patterns

Requirements:
    - sounddevice (for audio playback)
    - numpy (for audio processing)
"""

from pypulang import piece, I, IV, vi, V, Role, root_quarters, block_chords, arp

# =============================================================================
# Your composition - edit this and save to hear changes!
# =============================================================================

with piece(tempo=128, key="G minor") as p:
    verse = p.section("verse", bars=4)
    verse.harmony(I, IV, vi, V)

    # Bass line - try changing root_quarters to root_eighths
    verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

    # Chords - try changing block_chords to arp("up")
    verse.track("keys", role=Role.HARMONY).pattern(block_chords)


# =============================================================================
# Hot reload - watches this file and restarts playback on save
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("pyPuLang Hot Reload Demo")
    print("=" * 60)
    print()
    print("Music is now playing in a loop.")
    print("Edit this file and save to hear your changes!")
    print()
    print("Try changing:")
    print("  - tempo: 120 -> 140")
    print("  - key: 'C major' -> 'G major'")
    print("  - harmony: I, IV, vi, V -> I, V, vi, IV")
    print("  - pattern: root_quarters -> arp('up')")
    print()
    print("Press Ctrl+C to stop.")
    print("=" * 60)

    # Start watching - this blocks until Ctrl+C
    p.watch()
