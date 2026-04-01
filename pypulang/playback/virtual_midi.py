"""
Virtual MIDI backend using python-rtmidi.

This backend creates a virtual MIDI port that can be used to route
MIDI events to external DAWs, synthesizers, or other MIDI software.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from pypulang.playback.instruments import InstrumentBank
from pypulang.playback.protocols import BasePlaybackBackend, BasePlaybackHandle

if TYPE_CHECKING:
    import rtmidi


# Check if rtmidi is available
try:
    import rtmidi

    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False
    rtmidi = None  # type: ignore


class VirtualMidiHandle(BasePlaybackHandle):
    """
    Handle for controlling VirtualMidi playback.

    Manages the MIDI playback thread and provides transport controls.
    """

    def __init__(
        self,
        midi_out: rtmidi.MidiOut,
        events: list[tuple[int, float, float, int, int]],
        tempo: float,
    ) -> None:
        super().__init__()
        self._midi_out = midi_out
        self._events = events
        self._tempo = tempo
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._complete_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._current_index = 0
        self._active_notes: list[tuple[int, int]] = []  # (channel, pitch)

    def _start_playback(self) -> None:
        """Start the MIDI playback thread."""
        self._playing = True
        self._stopped = False
        self._current_index = 0

        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def _playback_loop(self) -> None:
        """Main playback loop running in a separate thread."""
        beats_per_second = self._tempo / 60.0
        start_time = time.time()

        # Sort events by start time
        sorted_events = sorted(self._events, key=lambda e: e[1])

        # Create note-off events
        all_events: list[tuple[float, str, int, int, int]] = []
        for pitch, start_beat, duration_beats, velocity, channel in sorted_events:
            all_events.append((start_beat, "on", pitch, velocity, channel))
            all_events.append((start_beat + duration_beats, "off", pitch, 0, channel))

        # Sort all events by time
        all_events.sort(key=lambda e: (e[0], 0 if e[1] == "off" else 1))

        event_index = 0
        while event_index < len(all_events) and not self._stopped:
            # Wait if paused
            self._pause_event.wait()

            if self._stopped:
                break

            beat_time, event_type, pitch, velocity, channel = all_events[event_index]
            target_time = start_time + beat_time / beats_per_second

            # Wait until it's time for this event
            current_time = time.time()
            if target_time > current_time:
                sleep_time = target_time - current_time
                # Use small sleep intervals to check for stop/pause
                while sleep_time > 0 and not self._stopped:
                    self._pause_event.wait()
                    if self._stopped:
                        break
                    time.sleep(min(sleep_time, 0.01))
                    sleep_time = target_time - time.time()

            if self._stopped:
                break

            # Send MIDI message
            if event_type == "on":
                self._midi_out.send_message([0x90 | channel, pitch, velocity])
                with self._lock:
                    self._active_notes.append((channel, pitch))
            else:  # off
                self._midi_out.send_message([0x80 | channel, pitch, 0])
                with self._lock:
                    if (channel, pitch) in self._active_notes:
                        self._active_notes.remove((channel, pitch))

            event_index += 1

        # Clean up
        self._stop_all_notes()
        self._playing = False
        self._complete_event.set()

    def _stop_all_notes(self) -> None:
        """Send note-off for all active notes."""
        with self._lock:
            for channel, pitch in self._active_notes:
                try:
                    self._midi_out.send_message([0x80 | channel, pitch, 0])
                except Exception:
                    pass
            self._active_notes.clear()

    def stop(self) -> None:
        """Stop playback immediately."""
        with self._lock:
            self._stopped = True
            self._playing = False
            self._pause_event.set()  # Unpause to allow thread to exit

        self._stop_all_notes()

        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

        self._complete_event.set()

    def pause(self) -> None:
        """Pause playback at current position."""
        with self._lock:
            if self._playing and not self._stopped:
                self._paused = True
                self._pause_event.clear()
                # Send note-off for all currently playing notes
                self._stop_all_notes()

    def resume(self) -> None:
        """Resume playback from paused position."""
        with self._lock:
            if self._paused:
                self._paused = False
                self._pause_event.set()

    def wait(self) -> None:
        """Block until playback completes or is stopped."""
        self._complete_event.wait()


class VirtualMidi(BasePlaybackBackend):
    """
    Virtual MIDI backend using python-rtmidi.

    Creates a virtual MIDI port that can be connected to DAWs
    or other MIDI software for playback with external instruments.

    Attributes:
        port_name: Name for the virtual MIDI port
    """

    def __init__(self, port_name: str = "pypulang") -> None:
        """
        Initialize the virtual MIDI backend.

        Args:
            port_name: Name for the virtual MIDI port
        """
        self._port_name = port_name
        self._midi_out: rtmidi.MidiOut | None = None
        self._connected = False

    def connect(self) -> bool:
        """
        Create and open the virtual MIDI port.

        Returns:
            True if connection successful, False otherwise
        """
        if not RTMIDI_AVAILABLE:
            return False

        try:
            self._midi_out = rtmidi.MidiOut()
            self._midi_out.open_virtual_port(self._port_name)
            self._connected = True
            return True
        except Exception as e:
            print(f"Failed to create virtual MIDI port: {e}")
            self._midi_out = None
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Close the virtual MIDI port."""
        if self._midi_out is not None:
            try:
                self._midi_out.close_port()
            except Exception:
                pass
            self._midi_out = None
            self._connected = False

    def play(
        self,
        events: list[tuple[int, float, float, int, str]],
        tempo: float,
        instruments: InstrumentBank | None = None,
    ) -> VirtualMidiHandle:
        """
        Start playback of the given events via MIDI.

        Note: The instruments parameter is ignored for VirtualMidi
        since sound is produced by external MIDI instruments.

        Args:
            events: List of note events as tuples:
                    (pitch, start_beat, duration_beats, velocity, track_name)
            tempo: Tempo in BPM
            instruments: Ignored (external instruments used)

        Returns:
            VirtualMidiHandle for transport control
        """
        if not RTMIDI_AVAILABLE:
            raise RuntimeError(
                "python-rtmidi is not installed. Install with: pip install pypulang[midi]"
            )

        # Auto-connect if not already connected
        if not self._connected:
            if not self.connect():
                raise RuntimeError(f"Failed to connect to MIDI port: {self._port_name}")

        # Convert track names to MIDI channels (simple mapping)
        track_to_channel: dict[str, int] = {}
        channel = 0

        midi_events: list[tuple[int, float, float, int, int]] = []
        for pitch, start, duration, velocity, track_name in events:
            if track_name not in track_to_channel:
                track_to_channel[track_name] = channel
                channel = (channel + 1) % 16
                # Skip channel 10 (drums)
                if channel == 9:
                    channel = 10

            midi_channel = track_to_channel[track_name]
            midi_events.append((pitch, start, duration, velocity, midi_channel))

        # Create and start handle
        handle = VirtualMidiHandle(self._midi_out, midi_events, tempo)
        handle._start_playback()
        return handle

    def list_ports(self) -> list[str]:
        """
        List available MIDI output ports.

        Returns:
            List of port names
        """
        if not RTMIDI_AVAILABLE:
            return []

        try:
            midi_out = rtmidi.MidiOut()
            ports = [midi_out.get_port_name(i) for i in range(midi_out.get_port_count())]
            return ports
        except Exception:
            return []

    def is_available(self) -> bool:
        """Check if python-rtmidi is available."""
        return RTMIDI_AVAILABLE

    def name(self) -> str:
        """Return backend name."""
        return f"VirtualMidi({self._port_name})"

    def __del__(self) -> None:
        """Clean up MIDI port on deletion."""
        self.disconnect()
