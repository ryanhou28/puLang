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

## Documentation

- [Style Guide](docs/style-guide.md) - Code style and formatting