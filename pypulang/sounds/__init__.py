"""
Ready-made sounds.

Racks here declare a song's instruments and shared effects in one call, so a song
file can stay about the music.
"""

from __future__ import annotations

from pypulang.dsl import PieceBuilder, Role, SectionBuilder, device, grid
from pypulang.ir.intent import Device
from pypulang.sounds.surge import (
    SURGE_XT,
    chop,
    clap,
    cutoff,
    electric_bass,
    gain,
    hat,
    impact,
    kick,
    mono_lead,
    pluck,
    ride,
    riser,
    snare,
    sub_bass,
    supersaw,
    surge,
    warm_pad,
)

__all__ = [
    "SURGE_XT",
    "sampler",
    "cutoff",
    "fusion_drums",
    "fusion_rack",
    "future_bass_rack",
    "eq",
    "surge",
]


def sampler(
    name: str,
    sounds: dict[int, str | dict] | list[dict],
    one_shot: bool = True,
    gain_db: float = 0.0,
) -> Device:
    """
    kaiDAW's sampler, with audio files on keys.

    Args:
        name: Local name, as for any device
        sounds: Key to a file path (relative to the song), or to a dict with "file" and
            any of "root", "low", "high", "gain", "pan", "one_shot", "low_velocity",
            "high_velocity" and "release" (milliseconds after the note ends). A bare
            path plays on its key alone, which is what a drum pad is. Or a list of
            such dicts, each with its "root", for several sounds on one key, as an
            instrument recorded at several dynamics has.
        one_shot: Whether a sound plays to its end however short the note is
        gain_db: The default gain of every sound

    Example:
        song.rack("drums", sampler("kit", {36: "samples/kick.wav", 38: "samples/snare.wav"}))
    """
    if isinstance(sounds, list):
        sounds_by_key = [(int(s["root"]), s) for s in sounds]
    else:
        sounds_by_key = sorted(sounds.items())
    specs = []
    for key, sound in sounds_by_key:
        spec = {"file": sound} if isinstance(sound, str) else dict(sound)
        spec.setdefault("root", key)
        spec.setdefault("low", key)
        spec.setdefault("high", key)
        spec.setdefault("gain", gain_db)
        spec.setdefault("pan", 0.0)
        spec.setdefault("one_shot", one_shot)
        specs.append(spec)
    return Device(name=name, identifier="sampler", params={}, sounds=specs)


# Tracktion's four-band EQ: each band's parameter names, and the ranges its
# normalised values span (linearly) in Hz, dB and Q.
_EQ_BANDS = {
    "low": ("Low-shelf freq", "Low-shelf gain", "Low-shelf Q"),
    "mid": ("Mid freq 1", "Mid gain 1", "Mid Q 1"),
    "mid2": ("Mid freq 2", "Mid gain 2", "Mid Q 2"),
    "high": ("High-shelf freq", "High-shelf gain", "High-shelf Q"),
}
_EQ_RANGES = ((20.0, 20000.0), (-20.0, 20.0), (0.1, 4.0))


def eq(
    name: str = "eq",
    *,
    low: tuple[float, ...] | None = None,
    mid: tuple[float, ...] | None = None,
    mid2: tuple[float, ...] | None = None,
    high: tuple[float, ...] | None = None,
) -> Device:
    """
    kaiDAW's four-band EQ in Hz and dB: a shelf at each end and two peaks between.

    Each band is (hz, db) or (hz, db, q); a band not given stays flat.

    Example:
        song.rack("trumpet", sampled("horn", "muted_trumpet"), eq(high=(3000, -5)))
    """
    params: dict[str, float] = {}
    for band, setting in (("low", low), ("mid", mid), ("mid2", mid2), ("high", high)):
        if setting is None:
            continue
        if len(setting) not in (2, 3):
            raise ValueError(f"eq {band}: give (hz, db) or (hz, db, q), not {setting!r}")
        for param, value, (lo, hi), unit in zip(
            _EQ_BANDS[band], setting, _EQ_RANGES, ("Hz", "dB", "Q"), strict=False
        ):
            if not lo <= value <= hi:
                raise ValueError(f"eq {band}: {value} {unit} is outside {lo:g} to {hi:g}")
            params[param] = (value - lo) / (hi - lo)
    return Device(name=name, identifier="4bandEq", params=params)


# Sampled drums' gains in dB, set so each sits where its Surge stand-in did: the
# mean of the peak and RMS differences measured on stems of the same bars. The
# sampler follows velocity more than the Surge patches did, so one set of bars
# cannot match everywhere; the fusion kit is matched on an A section, which is
# most of Slow Orbit, and its solo comes out a few dB softer.
FUSION_GAINS = {"kick": 4.0, "snare": 12.5, "hat": 15.0, "ride": 5.0}
FUTURE_GAINS = {"kick": -2.0, "clap": 16.5, "roll": 9.0, "hat": 11.5}

# Where each drum patch wants to be played.
KICK_NOTE = 31
SNARE_NOTE = 55
HAT_NOTE = 60
RIDE_NOTE = 84


def _reverb_bus(song: PieceBuilder, room: float, wet: float) -> None:
    verb = device("reverb", "reverb")
    verb.params.update({"Room Size": room, "Dry Level": 0.0, "Wet Level": wet})
    song.rack("verb", verb, volume=0.7)


def _master(song: PieceBuilder, threshold: float, output: float) -> None:
    """
    Gentle compression on the master bus, which is also where the headroom comes from.

    Args:
        threshold: Normalised (0.2 is -13.6 dB, 0.4 is -7.8 dB)
        output: Normalised (0.1 is -6.6 dB, 0.3 is +0.2 dB)
    """
    glue = device("glue", "compressor")
    glue.params.update(
        {"Threshold": threshold, "Ratio": 0.4, "Attack": 0.1, "Release": 0.3, "Output gain": output}
    )
    song.rack("master", glue)


def _drum(kit: str | None, file: str, key: int, synth: Device, gain_db: float = 0.0) -> Device:
    """A sampled drum when a kit folder is given, else the Surge patch that stood in for it."""
    if kit is None:
        return synth
    return sampler("kit", {key: f"{kit}/{file}"}, gain_db=gain_db)


def fusion_rack(song: PieceBuilder, kit: str | None = None) -> None:
    """
    The fusion band: Rhodes, bass, synth lead, pad, and a kit.

    Args:
        kit: A folder of drum samples, relative to the song, such as "samples/jazz"
            from `scripts/get_drum_samples.py`. Without one the drums are Surge.
    """
    _master(song, threshold=0.3, output=0.15)
    _reverb_bus(song, room=0.45, wet=0.5)
    # Surge's own factory patches, loaded whole. The parameter-built versions
    # (`electric_piano()`, `warm_pad()`) are still here for comparison.
    song.rack(
        "rhodes",
        surge("synth", patch="Keys/Soft Suitcase"),
        volume=0.62,
        pan=-0.12,
        sends={"verb": 0.2},
    )
    song.rack(
        "pad",
        surge("synth", patch="Pads/MKS-70 Warm Pad"),
        volume=0.5,
        pan=0.1,
        sends={"verb": 0.35},
    )
    song.rack("bass", surge("synth", electric_bass()), volume=0.68)
    song.rack("lead", surge("synth", mono_lead()), volume=0.62, pan=0.05, sends={"verb": 0.25})
    # Sample gains put each sampled drum where the Surge one sat, measured on the
    # solo's stems; the faders are unchanged.
    song.rack(
        "kick",
        _drum(kit, "kick.wav", KICK_NOTE, surge("synth", kick()), FUSION_GAINS["kick"]),
        volume=0.66,
    )
    song.rack(
        "snare",
        _drum(kit, "snare.wav", SNARE_NOTE, surge("synth", snare()), FUSION_GAINS["snare"]),
        volume=0.56,
        sends={"verb": 0.12},
    )
    song.rack(
        "hat",
        _drum(kit, "hihat-closed.wav", HAT_NOTE, surge("synth", hat()), FUSION_GAINS["hat"]),
        volume=0.5,
        pan=0.18,
    )
    song.rack(
        "ride",
        _drum(kit, "ride.wav", RIDE_NOTE, surge("synth", ride()), FUSION_GAINS["ride"]),
        volume=0.46,
        pan=-0.2,
    )


def fusion_drums(
    section: SectionBuilder, kick: str, snare: str, hat: str, step: float = 1 / 16
) -> None:
    """Write a groove as three cells, on the fusion kit."""
    section.track("kick", role=Role.RHYTHM).pattern(
        grid(cell=kick, step=step, pitch=KICK_NOTE)
    ).velocity(112)
    section.track("snare", role=Role.RHYTHM).pattern(
        grid(cell=snare, step=step, pitch=SNARE_NOTE)
    ).velocity(100)
    section.track("hat", role=Role.RHYTHM).pattern(
        grid(cell=hat, step=step, pitch=HAT_NOTE)
    ).velocity(82)


def future_bass_rack(song: PieceBuilder, kit: str | None = None) -> None:
    """
    Saws, a sub, plucks, a vowel lead, and a kit.

    Args:
        kit: A folder of drum samples, relative to the song, such as "samples/future"
            from `scripts/get_drum_samples.py`. Without one the drums are Surge.
    """
    _master(song, threshold=0.25, output=0.08)
    _reverb_bus(song, room=0.7, wet=0.6)
    song.rack("chords", surge("synth", supersaw()), volume=0.74, sends={"verb": 0.25})
    song.rack(
        "pad", surge("synth", warm_pad(), A_VCA_Gain=gain(-3)), volume=0.62, sends={"verb": 0.45}
    )
    song.rack(
        "pluck",
        surge("synth", pluck(), A_VCA_Gain=gain(-3)),
        volume=0.58,
        pan=-0.15,
        sends={"verb": 0.4},
    )
    song.rack("sub", surge("synth", sub_bass()), volume=0.74)
    song.rack("lead", surge("synth", mono_lead()), volume=0.6, sends={"verb": 0.4})
    song.rack("chop", surge("synth", chop()), volume=0.6, pan=0.1, sends={"verb": 0.4})
    song.rack(
        "kick", _drum(kit, "kick.wav", 31, surge("synth", kick()), FUTURE_GAINS["kick"]), volume=0.7
    )
    song.rack(
        "clap",
        _drum(kit, "clap.wav", 55, surge("synth", clap()), FUTURE_GAINS["clap"]),
        volume=0.6,
        sends={"verb": 0.25},
    )
    song.rack(
        "roll",
        _drum(kit, "snare.wav", 55, surge("synth", snare()), FUTURE_GAINS["roll"]),
        volume=0.52,
        sends={"verb": 0.3},
    )
    song.rack(
        "hat",
        _drum(kit, "hihat-closed.wav", 60, surge("synth", hat()), FUTURE_GAINS["hat"]),
        volume=0.48,
        pan=0.15,
    )
    song.rack("riser", surge("synth", riser()), volume=0.5, sends={"verb": 0.5})
    song.rack("impact", surge("synth", impact()), volume=0.55, sends={"verb": 0.6})
