"""
pypulang.playback - Real-time audio playback for pypulang.

This module provides:
- PlaybackBackend protocol for extensible playback backends
- BuiltinSynth backend using waveform synthesis (default)
- VirtualMidi backend for DAW integration
- Instrument system (Synth, InstrumentBank)
- Transport controls (play, stop, pause, loop)

Usage:
    from pypulang import piece, I, IV, vi, V, Role, root_quarters
    from pypulang.playback import Synth, InstrumentBank

    with piece(tempo=120, key="C major") as p:
        verse = p.section("verse", bars=4)
        verse.harmony(I, IV, vi, V)
        verse.track("bass", role=Role.BASS).pattern(root_quarters)

    # Play with default instruments
    p.play()

    # Play with custom instruments
    instruments = InstrumentBank({
        Role.BASS: Synth(waveform="saw", cutoff=400),
    })
    p.play(instruments=instruments)
"""

from pypulang.playback.config import (
    get_available_backends,
    get_default_backend,
    set_default_backend,
)
from pypulang.playback.instruments import Instrument, InstrumentBank, Synth
from pypulang.playback.protocols import PlaybackBackend, PlaybackHandle


# Lazy imports for optional backends
def _get_builtin_synth():
    """Get BuiltinSynth backend (requires sounddevice)."""
    from pypulang.playback.builtin_synth import BuiltinSynth

    return BuiltinSynth


def _get_virtual_midi():
    """Get VirtualMidi backend (requires python-rtmidi)."""
    from pypulang.playback.virtual_midi import VirtualMidi

    return VirtualMidi


# Make backends available but lazily loaded
try:
    from pypulang.playback.builtin_synth import BuiltinSynth
except ImportError:
    BuiltinSynth = None  # type: ignore

try:
    from pypulang.playback.virtual_midi import VirtualMidi
except ImportError:
    VirtualMidi = None  # type: ignore

__all__ = [
    # Protocols
    "PlaybackBackend",
    "PlaybackHandle",
    # Instruments
    "Instrument",
    "Synth",
    "InstrumentBank",
    # Backends (may be None if deps not installed)
    "BuiltinSynth",
    "VirtualMidi",
    # Configuration
    "get_default_backend",
    "set_default_backend",
    "get_available_backends",
]
