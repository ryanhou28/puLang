"""
Playback configuration and backend management.

Provides global default backend configuration and discovery of available backends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypulang.playback.protocols import PlaybackBackend


# Global default backend
_default_backend: PlaybackBackend | None = None


def get_default_backend() -> PlaybackBackend:
    """
    Get the default playback backend.

    Returns the globally configured default, or auto-detects the best
    available backend if none is set.

    Returns:
        PlaybackBackend instance

    Raises:
        RuntimeError: If no playback backends are available
    """
    global _default_backend

    if _default_backend is not None:
        return _default_backend

    # Auto-detect best available backend
    backends = get_available_backends()
    if not backends:
        raise RuntimeError(
            "No playback backends available. "
            "Required dependencies may not be installed correctly.\n"
            "Try reinstalling pypulang:\n"
            "  pip install -e .  # or: pip install pypulang\n\n"
            "Required packages: sounddevice, numpy, python-rtmidi"
        )

    # Prefer BuiltinSynth over VirtualMidi as default
    for backend in backends:
        if backend.name() == "BuiltinSynth":
            _default_backend = backend
            return _default_backend

    # Fall back to first available
    _default_backend = backends[0]
    return _default_backend


def set_default_backend(backend: PlaybackBackend) -> None:
    """
    Set the default playback backend.

    Args:
        backend: PlaybackBackend instance to use as default
    """
    global _default_backend
    _default_backend = backend


def get_available_backends() -> list[PlaybackBackend]:
    """
    Get all available playback backends.

    Checks which backends have their dependencies installed and
    returns instances of those that are available.

    Returns:
        List of available PlaybackBackend instances
    """
    backends = []

    # Try BuiltinSynth
    try:
        from pypulang.playback.builtin_synth import BuiltinSynth

        backend = BuiltinSynth()
        if backend.is_available():
            backends.append(backend)
    except ImportError:
        pass

    # Try VirtualMidi
    try:
        from pypulang.playback.virtual_midi import VirtualMidi

        backend = VirtualMidi()
        if backend.is_available():
            backends.append(backend)
    except ImportError:
        pass

    return backends


def reset_default_backend() -> None:
    """Reset the default backend to auto-detect on next use."""
    global _default_backend
    _default_backend = None
