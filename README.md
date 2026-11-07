# puLang

puLang compiles music. You write a song as intent: harmony, form, patterns. A pipeline of
dialects lowers it to the tracks, clips and notes of a real DAW project, with your plugins.
You can then edit it in the DAW and keep composing in source, because recompiling keeps your
edits.

```python
from pypulang import *

with piece(tempo=132, key="C major", title="Blue") as song:
    a = song.section("a", bars=8)
    a.chart("Dm9 G13 | Cmaj9 | Em7 A7alt | Dm9 G7alt")
    a.track("bass", role=Role.BASS).pattern(walking_bass)
    a.track("keys", role=Role.HARMONY).pattern(comp).voicing("rootless", 52, 72)
```

```sh
pulang ir song.py --stage score     # read the IR at any stage
pulang push song.py                 # make kaiDAW hold the song
pulang render song.py -o song.wav   # bounce it
```

[docs/compiler.md](docs/compiler.md) explains how it works and how to use it.
[examples/songs](examples/songs) has two complete songs: Slow Orbit, jazz fusion in D dorian
with a section in 7/8, and Afterglow, future bass in Ab.

The older design documents, [architecture](docs/architecture.md), [IR spec](docs/ir-spec.md)
and [roadmap](docs/roadmap.md), describe more than exists. Each now says at the top what was
built.

## Installation

```bash
pip install pypulang
```

## Development

For development, we recommend using a virtual environment to keep dependencies isolated.

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/puLang.git
cd puLang

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=pypulang
```

### Code Formatting

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for issues
ruff check .

# Fix auto-fixable issues
ruff check --fix .

# Format code
ruff format .
```

See [docs/style-guide.md](docs/style-guide.md) for full style guidelines.

## Virtual MIDI Setup (DAW Integration)

To route pypulang output to your DAW, you need a virtual MIDI port:

**macOS:** Enable IAC Driver
1. Open "Audio MIDI Setup" (Spotlight → "Audio MIDI Setup")
2. Window → Show MIDI Studio
3. Double-click "IAC Driver"
4. Check "Device is online"

**Windows:** Install loopMIDI
1. Download from [tobias-erichsen.de/software/loopmidi.html](https://www.tobias-erichsen.de/software/loopmidi.html)
2. Run loopMIDI and create a port

**Linux:** ALSA virtual ports work automatically.

Then in your code:
```python
from pypulang.playback import VirtualMidi
p.play(backend=VirtualMidi("pypulang"))
```

## Documentation

- [The compiler](docs/compiler.md) - How it works and how to use it
- [kaiDAW findings](docs/kaidaw-findings.md) - What the songs need from kaiDAW
- [Style Guide](docs/style-guide.md) - Code style and formatting