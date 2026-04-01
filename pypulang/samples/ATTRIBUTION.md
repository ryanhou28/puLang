# Attribution

This directory contains audio samples used for drum playback.

## Drum Samples

### Included Samples

All samples were created using the script `scripts/generate_drum_samples.py`:

**kick.ogg**
- Generator: pypulang development team
- Method: Synthesized using NumPy (pitch envelope sine wave + noise click)
- License: CC0 (Public Domain)
- Parameters: 150Hz->40Hz pitch sweep, exponential decay

**snare.ogg**
- Generator: pypulang development team
- Method: Synthesized using NumPy (dual-tone body + white noise)
- License: CC0 (Public Domain)
- Parameters: 180Hz + 330Hz tones with noise layer

**hihat_closed.ogg**
- Generator: pypulang development team
- Method: Synthesized using NumPy (filtered high-frequency noise)
- License: CC0 (Public Domain)
- Parameters: 8-14kHz harmonics, fast decay (50ms)

**hihat_open.ogg**
- Generator: pypulang development team
- Method: Synthesized using NumPy (filtered high-frequency noise)
- License: CC0 (Public Domain)
- Parameters: 8-14kHz harmonics, slow decay (400ms)

**crash.ogg**
- Generator: pypulang development team
- Method: Synthesized using NumPy (complex noise + multiple harmonics)
- License: CC0 (Public Domain)
- Parameters: 6-16kHz harmonics, long modulated decay

**ride.ogg**
- Generator: pypulang development team
- Method: Synthesized using NumPy (bell tone + shimmer)
- License: CC0 (Public Domain)
- Parameters: 1200Hz fundamental, high-frequency shimmer


### Regenerating Samples

To regenerate or customize the drum samples:

```bash
python scripts/generate_drum_samples.py
```

You can edit the synthesis parameters in the script to adjust pitch envelopes, decay times, harmonic content, and more.

## Using Your Own Samples

If you prefer recorded drum samples, you can replace these with your own:

1. Convert to OGG format (44.1kHz mono recommended)
2. Name them according to the mapping in `pypulang/playback/drum_sampler.py`:
   - `kick.ogg` - Kick drum
   - `snare.ogg` - Snare drum
   - `hihat_closed.ogg` - Closed hi-hat
   - `hihat_open.ogg` - Open hi-hat
   - `crash.ogg` - Crash cymbal
   - `ride.ogg` - Ride cymbal
3. Place them in this directory