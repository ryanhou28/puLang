# puLang


## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/puLang.git
cd puLang

# Install in development mode
pip install -e ".[dev]"
```

## Development

### Setup

```bash
# Install dev dependencies
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

#

## Documentation

- [Style Guide](docs/style-guide.md) - Code style and formatting

## Project Structure

```
pypulang/
├── __init__.py       # Package exports
├── ir/
│   ├── __init__.py
│   └── intent.py     # Intent IR dataclasses
├── scales.py         # Pitch and scale utilities
├── resolution.py     # Chord resolution (roman numeral -> MIDI)
└── patterns.py       # Pattern generators (root_quarters, arp, etc.)

tests/
├── test_intent_ir.py
├── test_scales_and_resolution.py
└── test_patterns.py

docs/
└── style-guide.md
```
