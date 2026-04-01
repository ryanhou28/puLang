"""
pyPuLang playback example - Play music directly from Python.

This example demonstrates the built-in playback system:

1. Basic playback with p.play()
2. Looping with p.loop()
3. Custom instruments with Synth and InstrumentBank
4. Virtual MIDI for DAW integration

Requirements (all included in core pypulang):
    - sounddevice (built-in synth)
    - numpy (audio processing)
    - python-rtmidi (virtual MIDI ports)
"""

from pypulang import piece, I, IV, vi, V, Role, root_quarters, block_chords, arp


def create_composition():
    """Create a simple 4-bar composition."""
    with piece(tempo=120, key="C major") as p:
        verse = p.section("verse", bars=4)
        verse.harmony(I, IV, vi, V)
        verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)
        verse.track("keys", role=Role.HARMONY).pattern(block_chords)
    return p


def create_multi_track_composition():
    """Create a more complex composition with multiple tracks."""
    with piece(tempo=100, key="G major") as p:
        verse = p.section("verse", bars=8)
        verse.harmony(I, vi, IV, V)
        verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
        verse.track("keys", role=Role.HARMONY).pattern(arp("up")).octave(0)
        verse.track("pad", role=Role.HARMONY).pattern(block_chords)

        chorus = p.section("chorus", bars=8)
        chorus.harmony(IV, V, I, vi)
        chorus.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
        chorus.track("keys", role=Role.HARMONY).pattern(block_chords)
    return p


# =============================================================================
# Example 1: Basic Playback
# =============================================================================

def example_basic_playback():
    """
    Basic playback using the built-in synthesizer.

    This is the simplest way to hear your composition - just call p.play()!
    """
    print("Example 1: Basic Playback")
    print("-" * 40)

    p = create_composition()

    print("Playing composition with built-in synth...")
    p.play()  # Blocks until playback completes

    print("Done!")


# =============================================================================
# Example 2: Non-blocking Playback with Transport Control
# =============================================================================

def example_transport_control():
    """
    Non-blocking playback with transport controls.

    Use wait=False to get a handle for controlling playback.
    """
    import time

    print("\nExample 2: Transport Control")
    print("-" * 40)

    p = create_composition()

    print("Starting playback (non-blocking)...")
    handle = p.play(wait=False)

    # Do other things while music plays
    time.sleep(2)

    print("Pausing...")
    handle.pause()
    time.sleep(1)

    print("Resuming...")
    handle.resume()

    # Wait for completion
    handle.wait()
    print("Done!")


# =============================================================================
# Example 3: Looping
# =============================================================================

def example_looping():
    """
    Loop a composition or section.

    Great for practicing or tweaking while listening.
    """
    import time

    print("\nExample 3: Looping")
    print("-" * 40)

    p = create_composition()

    print("Looping 3 times...")
    handle = p.loop(count=3)
    handle.wait()

    print("Done!")


# =============================================================================
# Example 4: Section Playback
# =============================================================================

def example_section_playback():
    """
    Play or loop specific sections.

    Useful for focusing on a particular part of your composition.
    """
    print("\nExample 4: Section Playback")
    print("-" * 40)

    p = create_multi_track_composition()

    print("Playing just the verse...")
    p.play(section="verse")

    print("Playing just the chorus...")
    p.play(section="chorus")

    print("Done!")


# =============================================================================
# Example 5: Custom Instruments
# =============================================================================

def example_custom_instruments():
    """
    Customize the sound using Synth and InstrumentBank.

    Different waveforms, envelopes, and filters for each track.
    """
    from pypulang.playback import Synth, InstrumentBank

    print("\nExample 5: Custom Instruments")
    print("-" * 40)

    p = create_composition()

    # Create custom instruments
    instruments = InstrumentBank({
        # Punchy bass with saw wave and low-pass filter
        Role.BASS: Synth(
            waveform="saw",
            attack=0.01,
            decay=0.1,
            sustain=0.8,
            release=0.1,
            filter_type="lowpass",
            cutoff=400,
        ),
        # Soft pad with triangle wave and slow attack
        Role.HARMONY: Synth(
            waveform="triangle",
            attack=0.2,
            decay=0.1,
            sustain=0.7,
            release=0.3,
        ),
    })

    print("Playing with custom instruments...")
    p.play(instruments=instruments)

    print("Done!")


# =============================================================================
# Example 6: Synth Presets
# =============================================================================

def example_synth_presets():
    """
    Use built-in synth presets for quick sound design.
    """
    from pypulang.playback import InstrumentBank, SynthBass, SynthPad, SynthLead

    print("\nExample 6: Synth Presets")
    print("-" * 40)

    p = create_composition()

    # Use preset synths
    instruments = InstrumentBank({
        Role.BASS: SynthBass(),      # Saw wave with low-pass filter
        Role.HARMONY: SynthPad(),    # Triangle wave with slow attack
        # SynthLead() is also available for melody lines
    })

    print("Playing with preset synths...")
    p.play(instruments=instruments)

    print("Done!")


# =============================================================================
# Example 7: Virtual MIDI (DAW Integration)
# =============================================================================

def example_virtual_midi():
    """
    Route MIDI to your DAW via a virtual MIDI port.

    Setup:
    - macOS: Use IAC Driver (Audio MIDI Setup > IAC Driver > enable)
    - Windows: Install loopMIDI (https://www.tobias-erichsen.de/software/loopmidi.html)
    - Linux: ALSA virtual ports (usually work out of the box)

    Then in your DAW:
    1. Create a MIDI track
    2. Set input to "pypulang" virtual port
    3. Arm the track for recording
    4. Run this example
    """
    from pypulang.playback import VirtualMidi

    print("\nExample 7: Virtual MIDI")
    print("-" * 40)

    p = create_composition()

    # List available MIDI ports
    ports = p.list_ports()
    print(f"Available MIDI ports: {ports}")

    # Create virtual MIDI port and play
    print("Creating virtual MIDI port 'pypulang'...")
    print("Connect your DAW to this port to hear the output.")

    try:
        midi_backend = VirtualMidi("pypulang")
        if midi_backend.is_available():
            print("Playing via virtual MIDI...")
            p.play(backend=midi_backend)
            print("Done!")
        else:
            print("python-rtmidi not available. Install with: pip install python-rtmidi")
    except Exception as e:
        print(f"Virtual MIDI error: {e}")
        print("Make sure you have virtual MIDI ports set up on your system.")


# =============================================================================
# Example 8: Start from Specific Bar
# =============================================================================

def example_from_bar():
    """
    Start playback from a specific bar.

    Useful for jumping to a specific part of a long composition.
    """
    print("\nExample 8: Start from Bar")
    print("-" * 40)

    p = create_multi_track_composition()

    print("Playing from bar 5 (middle of the piece)...")
    p.play(from_bar=5)

    print("Done!")


# =============================================================================
# Example 9: Hot Reload (Live Coding)
# =============================================================================

def example_hot_reload():
    """
    Enable hot reload for live coding.

    This watches the source file and automatically reloads when you save.
    Great for rapid iteration and live performance.

    Note: This example is best run from its own file. See examples/hot_reload.py
    for a standalone hot reload demo.
    """
    print("\nExample 9: Hot Reload")
    print("-" * 40)
    print("Hot reload watches your source file and restarts playback on save.")
    print("For the best experience, run examples/hot_reload.py directly:")
    print()
    print("    python examples/hot_reload.py")
    print()
    print("Then edit the file and save to hear your changes!")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("pyPuLang Playback Examples")
    print("=" * 60)

    # Run basic example by default
    example_basic_playback()

    # Uncomment to run other examples:
    # example_transport_control()
    # example_looping()
    # example_section_playback()
    # example_custom_instruments()
    # example_synth_presets()
    # example_virtual_midi()
    # example_from_bar()
    # example_hot_reload()

    print("\n" + "=" * 60)
    print("To run other examples, uncomment them in the main block.")
    print("For hot reload, run: python examples/hot_reload.py")
    print("=" * 60)
