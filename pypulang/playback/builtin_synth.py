"""
Built-in synthesizer backend using sounddevice.

This is the default playback backend that uses waveform synthesis
to produce audio output without requiring external dependencies
beyond sounddevice and numpy.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from pypulang.playback.instruments import InstrumentBank, get_default_instrument_bank
from pypulang.playback.protocols import BasePlaybackBackend, BasePlaybackHandle

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt


# Check if sounddevice is available
try:
    import numpy as np
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    sd = None  # type: ignore
    np = None  # type: ignore


class BuiltinSynthHandle(BasePlaybackHandle):
    """
    Handle for controlling BuiltinSynth playback.

    Manages the audio playback thread and provides transport controls.
    """

    def __init__(
        self,
        audio_data: npt.NDArray[np.float32],
        sample_rate: int,
    ) -> None:
        super().__init__()
        self._audio_data = audio_data
        self._sample_rate = sample_rate
        self._stream: sd.OutputStream | None = None
        self._position = 0
        self._lock = threading.Lock()
        self._complete_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially

    def _start_playback(self) -> None:
        """Start the audio stream."""
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("sounddevice not available")

        self._playing = True
        self._stopped = False
        self._position = 0

        def callback(
            outdata: npt.NDArray[np.float32],
            frames: int,
            time_info: dict,
            status: sd.CallbackFlags,
        ) -> None:
            # Wait if paused
            self._pause_event.wait()

            with self._lock:
                if self._stopped:
                    outdata.fill(0)
                    raise sd.CallbackStop()

                remaining = len(self._audio_data) - self._position
                if remaining <= 0:
                    outdata.fill(0)
                    self._complete_event.set()
                    raise sd.CallbackStop()

                chunk_size = min(frames, remaining)
                outdata[:chunk_size, 0] = self._audio_data[
                    self._position : self._position + chunk_size
                ]
                if chunk_size < frames:
                    outdata[chunk_size:] = 0
                self._position += chunk_size

        self._stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype=np.float32,
            callback=callback,
            finished_callback=self._on_finished,
        )
        self._stream.start()

    def _on_finished(self) -> None:
        """Called when stream finishes."""
        with self._lock:
            self._playing = False
            self._complete_event.set()

    def stop(self) -> None:
        """Stop playback immediately."""
        with self._lock:
            self._stopped = True
            self._playing = False
            self._pause_event.set()  # Unpause to allow callback to exit

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        self._complete_event.set()

    def pause(self) -> None:
        """Pause playback at current position."""
        with self._lock:
            if self._playing and not self._stopped:
                self._paused = True
                self._pause_event.clear()

    def resume(self) -> None:
        """Resume playback from paused position."""
        with self._lock:
            if self._paused:
                self._paused = False
                self._pause_event.set()

    def wait(self) -> None:
        """Block until playback completes or is stopped."""
        self._complete_event.wait()

    def get_position_seconds(self) -> float:
        """Get current playback position in seconds."""
        with self._lock:
            return self._position / self._sample_rate

    def get_position_beats(self, tempo: float) -> float:
        """
        Get current playback position in beats.

        Args:
            tempo: Tempo in BPM (needed to convert from seconds)

        Returns:
            Current position in beats
        """
        seconds = self.get_position_seconds()
        beats_per_second = tempo / 60.0
        return seconds * beats_per_second


class BuiltinSynth(BasePlaybackBackend):
    """
    Built-in synthesizer backend using sounddevice.

    Uses waveform synthesis to produce audio output. This is the
    default backend that works without external MIDI dependencies.

    Attributes:
        sample_rate: Audio sample rate (default 44100)
    """

    def __init__(self, sample_rate: int = 44100) -> None:
        """
        Initialize the built-in synth backend.

        Args:
            sample_rate: Audio sample rate in Hz
        """
        self._sample_rate = sample_rate

    def play(
        self,
        events: list[tuple[int, float, float, int, str, str]],
        tempo: float,
        instruments: InstrumentBank | None = None,
    ) -> BuiltinSynthHandle:
        """
        Start playback of the given events.

        Args:
            events: List of note events as tuples:
                    (pitch, start_beat, duration_beats, velocity, track_name, role)
            tempo: Tempo in BPM
            instruments: Optional InstrumentBank for sound assignment

        Returns:
            BuiltinSynthHandle for transport control
        """
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError(
                "sounddevice is not installed. Install with: pip install pypulang[playback]"
            )

        if instruments is None:
            instruments = get_default_instrument_bank()

        # Render all events to audio
        audio_data = self._render_events(events, tempo, instruments)

        # Create and start handle
        handle = BuiltinSynthHandle(audio_data, self._sample_rate)
        handle._start_playback()
        return handle

    def _render_events(
        self,
        events: list[tuple[int, float, float, int, str, str]],
        tempo: float,
        instruments: InstrumentBank,
    ) -> npt.NDArray[np.float32]:
        """Render all events to a single audio buffer."""
        if not events:
            return np.array([], dtype=np.float32)

        # Calculate total duration
        beats_per_second = tempo / 60.0
        seconds_per_beat = 1.0 / beats_per_second

        max_end_beat = 0.0
        for _pitch, start, duration, _velocity, _track, _role in events:
            end_beat = start + duration
            if end_beat > max_end_beat:
                max_end_beat = end_beat

        # Add some padding for release tails
        max_release = 0.5  # Assume max 0.5s release
        total_duration = max_end_beat * seconds_per_beat + max_release
        total_samples = int(total_duration * self._sample_rate)

        # Create output buffer
        output = np.zeros(total_samples, dtype=np.float32)

        # Render each event
        for pitch, start_beat, duration_beats, velocity, track_name, role in events:
            # Get instrument for track using the role from the event
            instrument = instruments.get_instrument(track_name, role)

            # Convert to seconds
            start_sec = start_beat * seconds_per_beat
            duration_sec = duration_beats * seconds_per_beat

            # Render note
            note_audio = instrument.render(pitch, duration_sec, velocity, self._sample_rate)

            # Mix into output
            start_sample = int(start_sec * self._sample_rate)
            end_sample = start_sample + len(note_audio)

            if end_sample > len(output):
                # Extend buffer if needed
                extra = end_sample - len(output)
                output = np.concatenate([output, np.zeros(extra, dtype=np.float32)])

            output[start_sample:end_sample] += note_audio

        # Normalize to prevent clipping
        max_amplitude = np.max(np.abs(output))
        if max_amplitude > 0.9:
            output = output * (0.9 / max_amplitude)

        return output

    def is_available(self) -> bool:
        """Check if sounddevice is available."""
        return SOUNDDEVICE_AVAILABLE

    def name(self) -> str:
        """Return backend name."""
        return "BuiltinSynth"
