"""
Ready-made sounds.

Racks here declare a song's instruments and shared effects in one call, so a song
file can stay about the music.
"""

from __future__ import annotations

from pypulang.dsl import PieceBuilder, Role, SectionBuilder, device, grid
from pypulang.sounds.surge import (
    SURGE_XT,
    chop,
    clap,
    cutoff,
    electric_bass,
    electric_piano,
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
    "cutoff",
    "fusion_drums",
    "fusion_rack",
    "future_bass_rack",
    "surge",
]

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


def fusion_rack(song: PieceBuilder) -> None:
    """The fusion band: Rhodes, bass, synth lead, pad, and a kit."""
    _master(song, threshold=0.3, output=0.18)
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
        "pad", surge("synth", patch="Pads/MKS-70 Warm Pad"), volume=0.5, pan=0.1, sends={"verb": 0.35}
    )
    song.rack("bass", surge("synth", electric_bass()), volume=0.68)
    song.rack("lead", surge("synth", mono_lead()), volume=0.62, pan=0.05, sends={"verb": 0.25})
    song.rack("kick", surge("synth", kick()), volume=0.66)
    song.rack("snare", surge("synth", snare()), volume=0.56, sends={"verb": 0.12})
    song.rack("hat", surge("synth", hat()), volume=0.5, pan=0.18)
    song.rack("ride", surge("synth", ride()), volume=0.46, pan=-0.2)


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


def future_bass_rack(song: PieceBuilder) -> None:
    """Saws, a sub, plucks, a vowel lead, and a kit."""
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
    song.rack("kick", surge("synth", kick()), volume=0.7)
    song.rack("clap", surge("synth", clap()), volume=0.6, sends={"verb": 0.25})
    song.rack("roll", surge("synth", snare()), volume=0.52, sends={"verb": 0.3})
    song.rack("hat", surge("synth", hat()), volume=0.48, pan=0.15)
    song.rack("riser", surge("synth", riser()), volume=0.5, sends={"verb": 0.5})
    song.rack("impact", surge("synth", impact()), volume=0.55, sends={"verb": 0.6})
