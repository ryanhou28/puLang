"""
pyPuLang playback example - Play MIDI directly from Python.

This example shows multiple ways to play your compositions:

1. pygame.mixer - Simple, cross-platform, but limited instrument choice
2. pyfluidsynth - Full SoundFont support, swap instruments easily
3. midi2audio - Convert to WAV/MP3 for sharing

Installation:
    pip install pygame              # Option 1: Simple playback
    pip install pyfluidsynth        # Option 2: Full synth (requires FluidSynth)
    pip install midi2audio          # Option 3: Render to audio file

For FluidSynth, you also need the system library:
    macOS:   brew install fluid-synth
    Ubuntu:  sudo apt-get install fluidsynth
    Windows: Download from https://github.com/FluidSynth/fluidsynth/releases
"""

from pypulang import *
import tempfile
import os

# Create a simple composition
def create_composition():
    with piece(tempo=120, key="C major") as p:
        verse = p.section("verse", bars=4)
        verse.harmony(I, IV, vi, V)
        verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)
        verse.track("keys", role=Role.HARMONY).pattern(block_chords)
    return p

# Option 1: pygame.mixer (simplest, works on most systems)
def play_with_pygame(p):
    """
    Play using pygame's built-in MIDI support.

    Pros: Simple, cross-platform, no external dependencies
    Cons: Uses system default synth, limited control over instruments
    """
    import pygame

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
        temp_path = f.name

    p.save_midi(temp_path)

    # Initialize pygame mixer
    pygame.mixer.init()
    pygame.mixer.music.load(temp_path)
    pygame.mixer.music.play()

    # Wait for playback to finish
    while pygame.mixer.music.get_busy():
        pygame.time.wait(100)

    pygame.mixer.quit()
    os.unlink(temp_path)
    print("Finished playing with pygame")


# Option 2: pyfluidsynth
def play_with_fluidsynth(p, soundfont_path=None):
    """
    Play using FluidSynth with SoundFont support.

    Pros: Full control over instruments, high quality sound, real-time
    Cons: Requires FluidSynth installation and a SoundFont file

    SoundFonts to try:
    - FluidR3_GM.sf2 (General MIDI, ~140MB, excellent quality)
    - TimGM6mb.sf2 (General MIDI, ~6MB, good for testing)
    - MuseScore_General.sf3 (from MuseScore, great quality)

    Download free SoundFonts:
    - https://musical-artifacts.com/artifacts?formats=sf2
    - https://github.com/FluidSynth/fluidsynth/wiki/SoundFont
    """
    import fluidsynth
    import tempfile
    import time

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
        temp_path = f.name
    p.save_midi(temp_path)

    # Create synth
    fs = fluidsynth.Synth()
    fs.start(driver="coreaudio")  # Use "alsa" on Linux, "dsound" on Windows

    # Load SoundFont
    if soundfont_path is None:
        # Common locations to check
        common_paths = [
            "/usr/share/sounds/sf2/FluidR3_GM.sf2",  # Linux
            "/usr/share/soundfonts/FluidR3_GM.sf2",  # Linux alt
            "/opt/homebrew/share/soundfonts/default.sf2",  # macOS Homebrew
            "~/soundfonts/FluidR3_GM.sf2",  # User directory
        ]
        for path in common_paths:
            expanded = os.path.expanduser(path)
            if os.path.exists(expanded):
                soundfont_path = expanded
                break

    if soundfont_path is None:
        print("No SoundFont found! Please download one and specify the path.")
        print("Try: https://musical-artifacts.com/artifacts?formats=sf2")
        return

    sfid = fs.sfload(soundfont_path)
    fs.program_select(0, sfid, 0, 0)  # Channel 0, bank 0, preset 0 (piano)

    # For more control, you can set specific instruments per channel:
    # fs.program_select(0, sfid, 0, 32)  # Acoustic Bass
    # fs.program_select(1, sfid, 0, 0)   # Piano

    # Play the MIDI file
    player = fluidsynth.Player(fs)
    player.add(temp_path)
    player.play()
    player.join()  # Wait for playback to complete

    fs.delete()
    os.unlink(temp_path)
    print("Finished playing with FluidSynth")


# Option 3: midi2audio (render to WAV/MP3)
def render_to_audio(p, output_path="output.wav", soundfont_path=None):
    """
    Render to WAV or MP3 file using midi2audio.

    Pros: Create shareable audio files, batch processing
    Cons: Not real-time, requires SoundFont
    """
    from midi2audio import FluidSynth
    import tempfile

    # Save MIDI to temp file
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
        temp_midi = f.name
    p.save_midi(temp_midi)

    # Convert to audio
    fs = FluidSynth(soundfont_path) if soundfont_path else FluidSynth()
    fs.midi_to_audio(temp_midi, output_path)

    os.unlink(temp_midi)
    print(f"Rendered to {output_path}")

def quick_play(p):
    """Try to play using available library, or just save the file."""
    try:
        play_with_pygame(p)
        return
    except ImportError:
        pass

    try:
        play_with_fluidsynth(p)
        return
    except ImportError:
        pass

    # Fallback: just save the file
    p.save_midi("output.mid")
    print("No playback library found. Saved to output.mid")
    print("Install pygame (pip install pygame) for simple playback")

# Main
if __name__ == "__main__":
    print("Creating composition...")
    p = create_composition()

    print("\nTrying to play...")
    quick_play(p)
