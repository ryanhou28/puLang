# puLang

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

- [Style Guide](docs/style-guide.md) - Code style and formatting