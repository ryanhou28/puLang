"""
Instrument system for pypulang playback.

Provides:
- Instrument base class
- Synth class for waveform synthesis
- InstrumentBank for mapping roles/tracks to instruments
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt


class Waveform(Enum):
    """Supported waveform types for synthesis."""

    SINE = "sine"
    SQUARE = "square"
    SAW = "saw"
    TRIANGLE = "triangle"


class FilterType(Enum):
    """Supported filter types."""

    LOWPASS = "lowpass"
    HIGHPASS = "highpass"


@dataclass
class Instrument(ABC):
    """
    Base class for all sound-producing instruments.

    Subclasses must implement the render() method to produce audio samples
    for a given note event.
    """

    @abstractmethod
    def render(
        self,
        pitch: int,
        duration: float,
        velocity: int,
        sample_rate: int,
    ) -> npt.NDArray[np.float32]:
        """
        Render a single note to audio samples.

        Args:
            pitch: MIDI pitch (0-127)
            duration: Duration in seconds
            velocity: MIDI velocity (0-127)
            sample_rate: Audio sample rate (e.g., 44100)

        Returns:
            Mono audio samples as float32 array, normalized to [-1, 1]
        """
        ...


@dataclass
class Synth(Instrument):
    """
    Waveform-based synthesizer with ADSR envelope.

    Generates audio from basic waveforms (sine, square, saw, triangle)
    with configurable envelope and optional filtering.

    Attributes:
        waveform: Type of waveform ("sine", "square", "saw", "triangle")
        attack: Attack time in seconds
        decay: Decay time in seconds
        sustain: Sustain level (0.0 to 1.0)
        release: Release time in seconds
        filter_type: Optional filter ("lowpass", "highpass", or None)
        cutoff: Filter cutoff frequency in Hz
    """

    waveform: str = "sine"
    attack: float = 0.01
    decay: float = 0.1
    sustain: float = 0.7
    release: float = 0.2
    filter_type: str | None = None
    cutoff: float = 1000.0

    def __post_init__(self) -> None:
        """Validate parameters."""
        valid_waveforms = {"sine", "square", "saw", "triangle"}
        if self.waveform not in valid_waveforms:
            raise ValueError(
                f"Invalid waveform: {self.waveform}. Must be one of: {valid_waveforms}"
            )

        if self.filter_type is not None:
            valid_filters = {"lowpass", "highpass"}
            if self.filter_type not in valid_filters:
                raise ValueError(
                    f"Invalid filter_type: {self.filter_type}. Must be one of: {valid_filters}"
                )

        if not 0 <= self.sustain <= 1:
            raise ValueError(f"Sustain must be 0-1, got {self.sustain}")

    def render(
        self,
        pitch: int,
        duration: float,
        velocity: int,
        sample_rate: int,
    ) -> npt.NDArray[np.float32]:
        """Render a note to audio samples."""
        import numpy as np

        # Convert MIDI pitch to frequency
        frequency = 440.0 * (2.0 ** ((pitch - 69) / 12.0))

        # Calculate total duration including release
        total_duration = duration + self.release
        num_samples = int(total_duration * sample_rate)

        if num_samples == 0:
            return np.array([], dtype=np.float32)

        # Generate time array
        t = np.linspace(0, total_duration, num_samples, dtype=np.float32)

        # Generate waveform
        if self.waveform == "sine":
            wave = np.sin(2 * np.pi * frequency * t)
        elif self.waveform == "square":
            wave = np.sign(np.sin(2 * np.pi * frequency * t))
        elif self.waveform == "saw":
            wave = 2 * (frequency * t % 1) - 1
        elif self.waveform == "triangle":
            wave = 2 * np.abs(2 * (frequency * t % 1) - 1) - 1
        else:
            wave = np.sin(2 * np.pi * frequency * t)

        # Apply ADSR envelope
        envelope = self._generate_envelope(duration, num_samples, sample_rate)
        wave = wave * envelope

        # Apply velocity scaling (velocity 0-127 maps to 0-1)
        velocity_scale = velocity / 127.0
        wave = wave * velocity_scale

        # Apply filter if specified
        if self.filter_type is not None:
            wave = self._apply_filter(wave, sample_rate)

        return wave.astype(np.float32)

    def _generate_envelope(
        self, note_duration: float, num_samples: int, sample_rate: int
    ) -> npt.NDArray[np.float32]:
        """Generate ADSR envelope."""
        import numpy as np

        envelope = np.zeros(num_samples, dtype=np.float32)

        attack_samples = int(self.attack * sample_rate)
        decay_samples = int(self.decay * sample_rate)
        release_samples = int(self.release * sample_rate)
        note_samples = int(note_duration * sample_rate)

        # Ensure we don't exceed buffer
        attack_samples = min(attack_samples, num_samples)
        decay_end = min(attack_samples + decay_samples, num_samples)
        sustain_end = min(note_samples, num_samples)
        release_end = min(sustain_end + release_samples, num_samples)

        # Attack phase
        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

        # Decay phase
        if decay_end > attack_samples:
            decay_len = decay_end - attack_samples
            envelope[attack_samples:decay_end] = np.linspace(1, self.sustain, decay_len)

        # Sustain phase
        if sustain_end > decay_end:
            envelope[decay_end:sustain_end] = self.sustain

        # Release phase
        if release_end > sustain_end:
            release_len = release_end - sustain_end
            start_level = envelope[sustain_end - 1] if sustain_end > 0 else self.sustain
            envelope[sustain_end:release_end] = np.linspace(start_level, 0, release_len)

        return envelope

    def _apply_filter(
        self, wave: npt.NDArray[np.float32], sample_rate: int
    ) -> npt.NDArray[np.float32]:
        """Apply a simple one-pole filter."""
        import numpy as np

        # Simple one-pole filter coefficient
        rc = 1.0 / (2.0 * np.pi * self.cutoff)
        dt = 1.0 / sample_rate

        if self.filter_type == "lowpass":
            alpha = dt / (rc + dt)
        else:  # highpass
            alpha = rc / (rc + dt)

        # Apply filter
        filtered = np.zeros_like(wave)
        filtered[0] = wave[0]

        if self.filter_type == "lowpass":
            for i in range(1, len(wave)):
                filtered[i] = filtered[i - 1] + alpha * (wave[i] - filtered[i - 1])
        else:  # highpass
            for i in range(1, len(wave)):
                filtered[i] = alpha * (filtered[i - 1] + wave[i] - wave[i - 1])

        return filtered.astype(np.float32)


# Preset synths
def SynthBass() -> Synth:
    """Preset: Bass synth with saw wave and low cutoff."""
    return Synth(
        waveform="saw",
        attack=0.01,
        decay=0.1,
        sustain=0.8,
        release=0.1,
        filter_type="lowpass",
        cutoff=400,
    )


def SynthPad() -> Synth:
    """Preset: Pad synth with triangle wave and slow envelope."""
    return Synth(
        waveform="triangle",
        attack=0.3,
        decay=0.2,
        sustain=0.7,
        release=0.5,
    )


def SynthLead() -> Synth:
    """Preset: Lead synth with square wave and fast attack."""
    return Synth(
        waveform="square",
        attack=0.01,
        decay=0.1,
        sustain=0.6,
        release=0.15,
    )


@dataclass
class DrumSampler(Instrument):
    """
    Sample-based drum instrument.

    Uses pre-recorded drum samples for realistic percussion sounds.
    Falls back to simple synthesis if samples are not available.

    Attributes:
        fallback_to_synth: If True, use synthesis when samples unavailable
    """

    fallback_to_synth: bool = True

    def render(
        self,
        pitch: int,
        duration: float,
        velocity: int,
        sample_rate: int,
    ) -> npt.NDArray[np.float32]:
        """Render a drum hit from samples or synthesis."""
        import numpy as np

        # Try to load drum sample
        try:
            from pypulang.playback.drum_sampler import render_drum_sample

            audio = render_drum_sample(pitch, duration, velocity, sample_rate)
            if audio is not None:
                return audio
        except ImportError:
            pass  # Fall through to synth

        # Fallback to synthesis
        if self.fallback_to_synth:
            return self._synthesize_drum(pitch, duration, velocity, sample_rate)
        else:
            # Return silence
            return np.zeros(int(duration * sample_rate), dtype=np.float32)

    def _synthesize_drum(
        self,
        pitch: int,
        duration: float,
        velocity: int,
        sample_rate: int,
    ) -> npt.NDArray[np.float32]:
        """
        Synthesize a drum sound (fallback when samples unavailable).

        Uses simple synthesis techniques for basic drum sounds.
        """
        import numpy as np

        # Map common drum pitches to synthesis methods
        if pitch in (35, 36):  # Kick
            return self._synth_kick(duration, velocity, sample_rate)
        elif pitch in (38, 40):  # Snare
            return self._synth_snare(duration, velocity, sample_rate)
        elif pitch in (42, 44, 46):  # Hi-hats
            return self._synth_hihat(duration, velocity, sample_rate, pitch == 46)
        else:
            # Generic percussive sound
            return self._synth_generic(pitch, duration, velocity, sample_rate)

    def _synth_kick(
        self, duration: float, velocity: int, sample_rate: int
    ) -> npt.NDArray[np.float32]:
        """Synthesize a kick drum."""
        import numpy as np

        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)

        # Pitch envelope (starts at 150Hz, drops to 40Hz)
        pitch_env = 150 * np.exp(-t * 30) + 40

        # Amplitude envelope (fast decay)
        amp_env = np.exp(-t * 15)

        # Generate sine wave with pitch envelope
        phase = 2 * np.pi * np.cumsum(pitch_env) / sample_rate
        wave = np.sin(phase, dtype=np.float32)

        # Add click at start
        click_env = np.exp(-t * 200)
        noise = np.random.randn(num_samples).astype(np.float32)
        click = noise * click_env * 0.3

        # Combine and apply envelope
        audio = (wave + click) * amp_env * (velocity / 127)

        return audio

    def _synth_snare(
        self, duration: float, velocity: int, sample_rate: int
    ) -> npt.NDArray[np.float32]:
        """Synthesize a snare drum."""
        import numpy as np

        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)

        # Body: two sine waves
        body1 = np.sin(2 * np.pi * 180 * t, dtype=np.float32)
        body2 = np.sin(2 * np.pi * 330 * t, dtype=np.float32)
        body = (body1 + body2) * 0.3

        # Noise (snare buzz)
        noise = np.random.randn(num_samples).astype(np.float32) * 0.7

        # Envelope (fast attack, medium decay)
        env = np.exp(-t * 20)

        # Combine
        audio = (body + noise) * env * (velocity / 127)

        return audio

    def _synth_hihat(
        self, duration: float, velocity: int, sample_rate: int, is_open: bool = False
    ) -> npt.NDArray[np.float32]:
        """Synthesize a hi-hat."""
        import numpy as np

        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)

        # Hi-hat is filtered white noise
        noise = np.random.randn(num_samples).astype(np.float32)

        # Envelope (very fast for closed, longer for open)
        decay_rate = 50 if not is_open else 15
        env = np.exp(-t * decay_rate)

        # High-pass filter (simple)
        # Apply envelope
        audio = noise * env * (velocity / 127) * 0.5

        return audio

    def _synth_generic(
        self, pitch: int, duration: float, velocity: int, sample_rate: int
    ) -> npt.NDArray[np.float32]:
        """Generic percussive sound for unmapped drum notes."""
        import numpy as np

        # Use pitch to frequency conversion, but with very fast decay
        frequency = 440.0 * (2.0 ** ((pitch - 69) / 12.0))

        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)

        # Fast decaying sine wave
        wave = np.sin(2 * np.pi * frequency * t, dtype=np.float32)
        env = np.exp(-t * 30)

        audio = wave * env * (velocity / 127)

        return audio


# Role enum import for type checking
try:
    from pypulang.dsl import Role
except ImportError:
    # Fallback for circular import issues
    Role = None  # type: ignore


class InstrumentBank:
    """
    Maps roles and track names to instruments.

    Allows configuring which instrument plays which track,
    either by musical role (BASS, MELODY, etc.) or by track name.
    Track names take precedence over roles.

    Example:
        instruments = InstrumentBank({
            Role.BASS: Synth(waveform="saw", cutoff=400),
            Role.HARMONY: Synth(waveform="triangle"),
            "lead": Synth(waveform="square"),  # Track name override
        })
    """

    def __init__(self, mapping: dict[Any, Instrument] | None = None) -> None:
        """
        Create an instrument bank.

        Args:
            mapping: Dict mapping Role enums or track names (str) to Instruments.
        """
        self._by_role: dict[str, Instrument] = {}
        self._by_name: dict[str, Instrument] = {}

        if mapping:
            for key, instrument in mapping.items():
                if isinstance(key, str):
                    self._by_name[key] = instrument
                elif hasattr(key, "value"):  # Role enum
                    self._by_role[key.value] = instrument
                else:
                    raise TypeError(
                        f"Invalid key type: {type(key)}. Expected Role enum or str (track name)."
                    )

    def get_instrument(self, track_name: str, role: str | None = None) -> Instrument:
        """
        Get instrument for a track.

        Checks track name first, then role, then returns default.

        Args:
            track_name: Name of the track
            role: Role string (e.g., "bass", "melody")

        Returns:
            Instrument to use for this track
        """
        # Check track name first
        if track_name in self._by_name:
            return self._by_name[track_name]

        # Check role
        if role and role in self._by_role:
            return self._by_role[role]

        # Return default
        return self._get_default_for_role(role)

    def _get_default_for_role(self, role: str | None) -> Instrument:
        """Get default instrument for a role."""
        if role == "bass":
            return Synth(waveform="saw", attack=0.01, filter_type="lowpass", cutoff=400)
        elif role == "harmony":
            return Synth(waveform="triangle", attack=0.05)
        elif role == "melody":
            return Synth(waveform="square", attack=0.01)
        elif role == "rhythm":
            # Use drum sampler for rhythm tracks (with synthesis fallback)
            return DrumSampler(fallback_to_synth=True)
        else:
            return Synth(waveform="sine")

    def set_instrument(self, key: Any, instrument: Instrument) -> InstrumentBank:
        """
        Set an instrument for a role or track name.

        Args:
            key: Role enum or track name string
            instrument: Instrument to use

        Returns:
            self for method chaining
        """
        if isinstance(key, str):
            self._by_name[key] = instrument
        elif hasattr(key, "value"):  # Role enum
            self._by_role[key.value] = instrument
        else:
            raise TypeError(
                f"Invalid key type: {type(key)}. Expected Role enum or str (track name)."
            )
        return self


# Default instrument bank
_DEFAULT_INSTRUMENT_BANK = InstrumentBank()


def get_default_instrument_bank() -> InstrumentBank:
    """Get the default instrument bank."""
    return _DEFAULT_INSTRUMENT_BANK
