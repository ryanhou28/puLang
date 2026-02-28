"""
Generate synthetic drum samples for pypulang.

Samples are saved as OGG files for good compression and quality.
"""

import numpy as np
import soundfile as sf
from pathlib import Path


def generate_kick(sample_rate=44100, duration=0.5):
    """Generate a kick drum sound."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Pitch envelope (starts at 150Hz, drops to 40Hz)
    pitch_env = 150 * np.exp(-t * 30) + 40

    # Generate sine wave with pitch envelope
    phase = 2 * np.pi * np.cumsum(pitch_env) / sample_rate
    wave = np.sin(phase)

    # Amplitude envelope (fast decay)
    amp_env = np.exp(-t * 15)

    # Add click at start for attack
    click_env = np.exp(-t * 200)
    noise = np.random.randn(len(t)) * 0.3
    click = noise * click_env

    # Combine
    audio = (wave + click) * amp_env

    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.9

    return audio.astype(np.float32)


def generate_snare(sample_rate=44100, duration=0.3):
    """Generate a snare drum sound."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Body: two sine waves (fundamental frequencies)
    body1 = np.sin(2 * np.pi * 180 * t)
    body2 = np.sin(2 * np.pi * 330 * t)
    body = (body1 + body2) * 0.4

    # Noise (snare buzz/rattle)
    noise = np.random.randn(len(t)) * 0.6

    # Envelope (fast attack, medium decay)
    env = np.exp(-t * 20)

    # Combine
    audio = (body + noise) * env

    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.9

    return audio.astype(np.float32)


def generate_hihat_closed(sample_rate=44100, duration=0.1):
    """Generate a closed hi-hat sound."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Hi-hat is primarily filtered white noise
    noise = np.random.randn(len(t))

    # High-pass filter (simple)
    # Use multiple sine waves at high frequencies
    harmonics = np.zeros(len(t))
    for freq in [8000, 10000, 12000, 14000]:
        harmonics += np.sin(2 * np.pi * freq * t) * 0.15

    # Combine noise and harmonics
    audio = noise * 0.7 + harmonics

    # Very fast decay envelope
    env = np.exp(-t * 50)
    audio = audio * env

    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.7  # Quieter than kick/snare

    return audio.astype(np.float32)


def generate_hihat_open(sample_rate=44100, duration=0.4):
    """Generate an open hi-hat sound."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Similar to closed but longer decay
    noise = np.random.randn(len(t))

    # High frequencies
    harmonics = np.zeros(len(t))
    for freq in [8000, 10000, 12000, 14000]:
        harmonics += np.sin(2 * np.pi * freq * t) * 0.15

    audio = noise * 0.7 + harmonics

    # Slower decay for open hi-hat
    env = np.exp(-t * 15)
    audio = audio * env

    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.7

    return audio.astype(np.float32)


def generate_crash(sample_rate=44100, duration=2.0):
    """Generate a crash cymbal sound."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Crash is complex noise with many harmonics
    noise = np.random.randn(len(t))

    # Add multiple high-frequency components
    harmonics = np.zeros(len(t))
    for freq in [6000, 8000, 10000, 12000, 14000, 16000]:
        phase = 2 * np.pi * freq * t + np.random.rand() * 2 * np.pi
        harmonics += np.sin(phase) * 0.1

    audio = noise * 0.6 + harmonics

    # Long decay envelope with some modulation
    env = np.exp(-t * 3) * (1 + 0.1 * np.sin(2 * np.pi * 7 * t))
    audio = audio * env

    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.8

    return audio.astype(np.float32)


def generate_ride(sample_rate=44100, duration=1.5):
    """Generate a ride cymbal sound."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Ride has a clear bell tone plus shimmer
    # Bell tone (around 1200Hz)
    bell = np.sin(2 * np.pi * 1200 * t) * 0.3
    bell += np.sin(2 * np.pi * 2400 * t) * 0.15  # Harmonic

    # Shimmer (high-frequency noise)
    noise = np.random.randn(len(t)) * 0.4

    # High harmonics
    harmonics = np.zeros(len(t))
    for freq in [8000, 10000, 12000]:
        harmonics += np.sin(2 * np.pi * freq * t) * 0.08

    audio = bell + noise + harmonics

    # Medium decay
    env = np.exp(-t * 4)
    audio = audio * env

    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.75

    return audio.astype(np.float32)


def main():
    """Generate all drum samples."""
    output_dir = Path(__file__).parent.parent / "pypulang" / "samples" / "drums"
    output_dir.mkdir(parents=True, exist_ok=True)

    sample_rate = 44100

    print("Generating synthetic drum samples...")
    print(f"Output directory: {output_dir}")

    # Generate samples
    samples = {
        "kick.ogg": generate_kick(sample_rate),
        "snare.ogg": generate_snare(sample_rate),
        "hihat_closed.ogg": generate_hihat_closed(sample_rate),
        "hihat_open.ogg": generate_hihat_open(sample_rate),
        "crash.ogg": generate_crash(sample_rate),
        "ride.ogg": generate_ride(sample_rate),
    }

    # Save as OGG files
    for filename, audio in samples.items():
        output_path = output_dir / filename
        sf.write(output_path, audio, sample_rate, format='OGG', subtype='VORBIS')
        file_size = output_path.stat().st_size / 1024  # KB
        print(f"  Generated {filename} ({file_size:.1f} KB)")

    print("\nDone! Samples are ready to use.")

if __name__ == "__main__":
    main()