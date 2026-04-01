# pyPuLang Examples

## Running Examples

From the project root directory:

```bash
# Run with PYTHONPATH
PYTHONPATH=. python examples/minimal.py

# Or install the package first
pip install -e .
python examples/minimal.py
```

## Examples

### [minimal.py](minimal.py)
The simplest example - a 4-bar bass line over I-IV-vi-V.

### [multi_track.py](multi_track.py)
Multiple tracks (bass + keys) with intro and verse sections.

### [instrument_swap.py](instrument_swap.py)
Shows how to quickly prototype with different General MIDI instruments.

### [playback.py](playback.py)
Different options for playing MIDI directly from Python.

## Playing Your MIDI Files

### Option 1: pygame (simplest)
```bash
pip install pygame
```
Uses system default synth. Simple but limited control.

### Option 2: FluidSynth (recommended for prototyping)
```bash
# Install FluidSynth
brew install fluid-synth        # macOS
sudo apt-get install fluidsynth # Ubuntu

# Install Python bindings
pip install pyfluidsynth
```
Requires a SoundFont file (.sf2). Download free ones from:
- https://musical-artifacts.com/artifacts?formats=sf2
- Popular choice: FluidR3_GM.sf2 (~140MB, great quality)

### Option 3: DAW
Open the .mid files directly in GarageBand, Logic, Ableton, FL Studio, etc.

### Option 4: Online
Upload to https://signal.vercel.app/edit or similar web MIDI players.
