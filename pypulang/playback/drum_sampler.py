"""
Drum sampler for built-in playback.

Loads and plays drum samples for percussion sounds.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import numpy as np

# Lazy import for audio loading
_SOUNDFILE_AVAILABLE = False
try:
    import soundfile as sf

    _SOUNDFILE_AVAILABLE = True
except ImportError:
    pass


# Map MIDI note numbers to sample filenames
DRUM_SAMPLE_MAP = {
    35: "kick.ogg",  # KICK2
    36: "kick.ogg",  # KICK (primary)
    37: "rimshot.ogg",  # RIMSHOT
    38: "snare.ogg",  # SNARE (primary)
    39: "clap.ogg",  # CLAP
    40: "snare.ogg",  # SNARE2 (use same as snare)
    42: "hihat_closed.ogg",  # HIHAT_CLOSED
    44: "hihat_closed.ogg",  # HIHAT_PEDAL (use closed)
    46: "hihat_open.ogg",  # HIHAT_OPEN
    49: "crash.ogg",  # CRASH
    51: "ride.ogg",  # RIDE
    53: "ride.ogg",  # RIDE_BELL (use same as ride)
    54: "tambourine.ogg",  # TAMBOURINE
    56: "cowbell.ogg",  # COWBELL
    57: "crash.ogg",  # CRASH2 (use same as crash)
}

# Sample cache to avoid reloading
_sample_cache: dict[int, np.ndarray | None] = {}


def get_samples_dir() -> Path:
    """Get the path to the bundled samples directory."""
    return Path(__file__).parent.parent / "samples" / "drums"


def load_drum_sample(midi_note: int, sample_rate: int = 44100) -> np.ndarray | None:
    """
    Load a drum sample for the given MIDI note.

    Args:
        midi_note: MIDI note number (e.g., 36 for kick)
        sample_rate: Target sample rate (for resampling if needed)

    Returns:
        Numpy array of audio samples, or None if sample not found
    """
    # Check cache first
    if midi_note in _sample_cache:
        return _sample_cache[midi_note]

    # Check if we have a mapping for this note
    if midi_note not in DRUM_SAMPLE_MAP:
        _sample_cache[midi_note] = None
        return None

    # Get sample filename
    sample_filename = DRUM_SAMPLE_MAP[midi_note]
    sample_path = get_samples_dir() / sample_filename

    # Check if file exists
    if not sample_path.exists():
        # Don't warn for every missing sample, just cache None
        _sample_cache[midi_note] = None
        return None

    # Check if soundfile is available
    if not _SOUNDFILE_AVAILABLE:
        if midi_note not in _sample_cache:
            warnings.warn(
                "soundfile not available - drum samples cannot be loaded. "
                "Install with: pip install soundfile",
                stacklevel=2,
            )
        _sample_cache[midi_note] = None
        return None

    try:
        # Load the audio file
        audio, file_sr = sf.read(sample_path, dtype="float32")

        # Convert stereo to mono if needed
        if audio.ndim == 2:
            audio = audio.mean(axis=1)

        # Resample if needed (simple resampling)
        if file_sr != sample_rate:
            audio = _simple_resample(audio, file_sr, sample_rate)

        # Cache and return
        _sample_cache[midi_note] = audio
        return audio

    except Exception as e:
        warnings.warn(f"Failed to load drum sample {sample_filename}: {e}", stacklevel=2)
        _sample_cache[midi_note] = None
        return None


def _simple_resample(audio: np.ndarray, old_sr: int, new_sr: int) -> np.ndarray:
    """
    Simple linear resampling (not high quality, but fast and good enough).

    For better quality, could use scipy.signal.resample, but we want
    to avoid heavy dependencies.
    """
    if old_sr == new_sr:
        return audio

    # Calculate new length
    duration = len(audio) / old_sr
    new_length = int(duration * new_sr)

    # Simple linear interpolation
    old_indices = np.linspace(0, len(audio) - 1, new_length)
    resampled = np.interp(old_indices, np.arange(len(audio)), audio)

    return resampled.astype(np.float32)


def render_drum_sample(
    midi_note: int,
    duration: float,
    velocity: int,
    sample_rate: int = 44100,
) -> np.ndarray | None:
    """
    Render a drum sample with velocity scaling.

    Args:
        midi_note: MIDI note number
        duration: Duration in seconds (may be shorter than sample)
        velocity: MIDI velocity (0-127)
        sample_rate: Sample rate in Hz

    Returns:
        Audio array, or None if sample not available
    """
    # Load the sample
    sample = load_drum_sample(midi_note, sample_rate)
    if sample is None:
        return None

    # Calculate velocity scaling (velocity affects amplitude)
    velocity_scale = velocity / 127.0

    # Calculate number of samples needed
    num_samples = int(duration * sample_rate)

    # Trim or pad sample to match duration
    if len(sample) > num_samples:
        # Trim
        audio = sample[:num_samples]
    else:
        # Pad with zeros
        audio = np.pad(sample, (0, num_samples - len(sample)), mode="constant")

    # Apply velocity scaling
    audio = audio * velocity_scale

    return audio


def has_drum_samples() -> bool:
    """
    Check if drum samples are available.

    Returns:
        True if at least one drum sample file exists
    """
    samples_dir = get_samples_dir()
    if not samples_dir.exists():
        return False

    # Check for at least one core sample
    core_samples = ["kick.ogg", "snare.ogg", "hihat_closed.ogg"]
    return any((samples_dir / sample).exists() for sample in core_samples)


def clear_sample_cache():
    """Clear the sample cache (useful for testing)."""
    global _sample_cache
    _sample_cache.clear()