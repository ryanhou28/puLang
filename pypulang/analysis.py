"""
Measuring rendered audio.

A compiler for music needs the same thing any compiler needs: a way to check its
output that does not depend on someone's ears being available. These numbers cannot
say whether a mix is good, but they catch silence, clipping, a bass line that
vanished, and an instrument that is not playing the pitch it was told to.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import soundfile as sf

BANDS = (
    ("sub", 20, 60),
    ("bass", 60, 250),
    ("low mid", 250, 1000),
    ("mid", 1000, 4000),
    ("high", 4000, 16000),
)


def to_db(value: float) -> float:
    return 20 * float(np.log10(max(value, 1e-9)))


@dataclass
class Span:
    """One stretch of audio, measured."""

    name: str
    rms_db: float
    peak: float
    centroid: float
    bands: dict[str, float]


def load(path: str, mono: bool = True) -> tuple[np.ndarray, int]:
    """
    Read a WAV as floats, mixed to mono unless `mono` is False.

    Clipping must be looked for in the channels: a mono mix averages a clipped
    left channel with an unclipped right and hides it. `clipped_samples` takes
    either.
    """
    audio, rate = sf.read(path, always_2d=True)
    return (audio.mean(axis=1) if mono else audio), rate


def _spectrum(samples: np.ndarray, rate: int) -> tuple[np.ndarray, np.ndarray]:
    window = np.hanning(len(samples))
    power = np.abs(np.fft.rfft(samples * window)) ** 2
    return np.fft.rfftfreq(len(samples), 1 / rate), power


def measure(samples: np.ndarray, rate: int, name: str = "") -> Span:
    """Loudness, peak, brightness and band balance of some samples."""
    if len(samples) == 0:
        return Span(name, -180.0, 0.0, 0.0, {})
    frequencies, power = _spectrum(samples, rate)
    total = float(power.sum()) or 1e-12
    bands = {
        label: 10
        * float(
            np.log10(max(power[(frequencies >= low) & (frequencies < high)].sum() / total, 1e-12))
        )
        for label, low, high in BANDS
    }
    return Span(
        name=name,
        rms_db=to_db(float(np.sqrt(np.mean(samples**2)))),
        peak=float(np.abs(samples).max()),
        centroid=float((frequencies * power).sum() / total),
        bands=bands,
    )


def sections(path: str, spans: list[tuple[str, float, float]]) -> list[Span]:
    """Measure named stretches of a file. Each is (name, start seconds, end seconds)."""
    samples, rate = load(path)
    return [measure(samples[int(a * rate) : int(b * rate)], rate, name) for name, a, b in spans]


def envelope(samples: np.ndarray, rate: int, window_ms: float = 5.0) -> np.ndarray:
    """RMS level over short windows."""
    size = max(1, int(rate * window_ms / 1000))
    usable = len(samples) // size * size
    return np.sqrt((samples[:usable].reshape(-1, size) ** 2).mean(axis=1))


def dominant_frequency(samples: np.ndarray, rate: int) -> float:
    """The strongest frequency, refined between FFT bins."""
    frequencies, power = _spectrum(samples, rate)
    peak = int(np.argmax(power[1:])) + 1
    if 0 < peak < len(power) - 1:
        a, b, c = np.log(power[peak - 1 : peak + 2] + 1e-20)
        shift = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) else 0.0
        return float(frequencies[peak] + shift * (frequencies[1] - frequencies[0]))
    return float(frequencies[peak])


def pitch_track(samples: np.ndarray, rate: int, window_ms: float = 12.0) -> list[float]:
    """The dominant frequency over time, for checking a pitch sweep."""
    size = int(rate * window_ms / 1000)
    return [
        dominant_frequency(samples[i : i + size * 4], rate)
        for i in range(0, len(samples) - size * 4, size)
    ]


def clipped_samples(samples: np.ndarray, threshold: float = 0.999) -> int:
    """Frames at or past `threshold` in any channel."""
    level = np.abs(samples)
    return int(((level.max(axis=1) if level.ndim == 2 else level) >= threshold).sum())


def report(spans: list[Span]) -> str:
    """A table of measurements."""
    lines = [
        f"{'':14s}{'RMS dB':>8s}{'peak':>7s}{'centroid':>10s}  "
        + " ".join(f"{b[0]:>8s}" for b in BANDS)
    ]
    for span in spans:
        bands = " ".join(f"{span.bands.get(b[0], -120):8.1f}" for b in BANDS)
        lines.append(
            f"{span.name:14s}{span.rms_db:8.1f}{span.peak:7.3f}{span.centroid:10.0f}  {bands}"
        )
    return "\n".join(lines)
