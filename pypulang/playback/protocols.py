"""
Playback protocols defining the interface for all playback backends.

These protocols ensure that all backends (BuiltinSynth, VirtualMidi, etc.)
provide a consistent API for playback control.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pypulang.playback.instruments import InstrumentBank


@runtime_checkable
class PlaybackHandle(Protocol):
    """
    Handle for controlling active playback.

    Returned by PlaybackBackend.play() to allow transport control
    of the currently playing piece.
    """

    def stop(self) -> None:
        """Stop playback immediately."""
        ...

    def pause(self) -> None:
        """Pause playback at current position."""
        ...

    def resume(self) -> None:
        """Resume playback from paused position."""
        ...

    def is_playing(self) -> bool:
        """Return True if playback is active (not paused or stopped)."""
        ...

    def is_paused(self) -> bool:
        """Return True if playback is paused."""
        ...

    def wait(self) -> None:
        """Block until playback completes or is stopped."""
        ...

    def get_position_seconds(self) -> float:
        """Get current playback position in seconds (optional)."""
        ...

    def get_position_beats(self, tempo: float) -> float:
        """Get current playback position in beats (optional)."""
        ...


@runtime_checkable
class PlaybackBackend(Protocol):
    """
    Protocol for all playback backends.

    Backends convert realized MIDI events to audio output through
    different mechanisms (built-in synth, virtual MIDI ports, etc.).
    """

    def play(
        self,
        events: list[tuple[int, float, float, int, str]],
        tempo: float,
        instruments: InstrumentBank | None = None,
    ) -> PlaybackHandle:
        """
        Start playback of the given events.

        Args:
            events: List of note events as tuples:
                    (pitch, start_beat, duration_beats, velocity, track_name)
            tempo: Tempo in BPM
            instruments: Optional InstrumentBank for sound assignment

        Returns:
            PlaybackHandle for transport control
        """
        ...

    def is_available(self) -> bool:
        """
        Check if this backend can be used.

        Returns False if required dependencies are not installed
        or if the system doesn't support this backend.
        """
        ...

    def name(self) -> str:
        """Return human-readable backend name."""
        ...


class BasePlaybackHandle(ABC):
    """
    Abstract base class for PlaybackHandle implementations.

    Provides common state management for playback handles.
    """

    def __init__(self) -> None:
        self._playing = False
        self._paused = False
        self._stopped = False

    def is_playing(self) -> bool:
        """Return True if playback is active (not paused or stopped)."""
        return self._playing and not self._paused and not self._stopped

    def is_paused(self) -> bool:
        """Return True if playback is paused."""
        return self._paused and not self._stopped

    @abstractmethod
    def stop(self) -> None:
        """Stop playback immediately."""
        ...

    @abstractmethod
    def pause(self) -> None:
        """Pause playback at current position."""
        ...

    @abstractmethod
    def resume(self) -> None:
        """Resume playback from paused position."""
        ...

    @abstractmethod
    def wait(self) -> None:
        """Block until playback completes or is stopped."""
        ...

    def get_position_seconds(self) -> float:
        """
        Get current playback position in seconds.

        Default implementation returns 0.0. Subclasses should override
        for accurate position tracking.
        """
        return 0.0

    def get_position_beats(self, tempo: float) -> float:
        """
        Get current playback position in beats.

        Args:
            tempo: Tempo in BPM (needed to convert from seconds)

        Returns:
            Current position in beats

        Default implementation converts from seconds. Subclasses can override.
        """
        seconds = self.get_position_seconds()
        beats_per_second = tempo / 60.0
        return seconds * beats_per_second


class BasePlaybackBackend(ABC):
    """
    Abstract base class for PlaybackBackend implementations.

    Provides common functionality for all backends.
    """

    @abstractmethod
    def play(
        self,
        events: list[tuple[int, float, float, int, str]],
        tempo: float,
        instruments: InstrumentBank | None = None,
    ) -> PlaybackHandle:
        """Start playback of the given events."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend can be used."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Return human-readable backend name."""
        ...
