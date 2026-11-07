"""
Surge XT as a set of named values.

A host sees Surge's controls as normalised numbers from 0 to 1. The tables and
curves here turn those back into words and units. Every value was measured against
the running plugin by writing a number and reading back what it displayed, and the
curves were fitted to those readings.

Patches are plain dictionaries of published parameter name to value, so they can be
merged, tweaked, and read.
"""

from __future__ import annotations

import math

from pypulang.ir.intent import Device

SURGE_XT = "VST3-Surge XT-1e1bcfb-190e4fbd"

OSC = {
    "classic": 0.0234375,
    "sine": 0.09375,
    "wavetable": 0.1796875,
    "noise": 0.2734375,
    "fm3": 0.453125,
    "fm2": 0.5390625,
    "window": 0.6328125,
    "modern": 0.7265625,
    "string": 0.8203125,
    "twist": 0.90625,
    "alias": 0.9765625,
}

FILTER = {
    "off": 0.0078125,
    "lp12": 0.0390625,
    "lp24": 0.0703125,
    "legacy": 0.1015625,
    "hp12": 0.125,
    "hp24": 0.1484375,
    "bp12": 0.1796875,
    "notch12": 0.2109375,
    "ladder": 0.3046875,
    "obxd12": 0.3359375,
    "obxd24": 0.3671875,
    "k35": 0.3984375,
    "diode": 0.4609375,
    "bp24": 0.6953125,
}

PLAY_MODE = {"poly": 0.046875, "mono": 0.203125}

UNISON = {
    1: 0.015625,
    2: 0.0703125,
    3: 0.1328125,
    4: 0.203125,
    5: 0.2734375,
    6: 0.3359375,
    7: 0.3984375,
    8: 0.4609375,
    9: 0.53125,
}

FX = {
    "off": 0.0078125,
    "delay": 0.0390625,
    "reverb1": 0.0703125,
    "phaser": 0.1015625,
    "rotary": 0.140625,
    "distortion": 0.1796875,
    "eq": 0.2109375,
    "chorus": 0.3125,
    "reverb2": 0.3828125,
    "flanger": 0.4140625,
    "ensemble": 0.6875,
    "tape": 0.7890625,
}


def seconds(value: float) -> float:
    """An envelope time. Surge's envelopes run from 2^-8 to 2^5 seconds."""
    return min(1.0, max(0.0, (math.log2(value) + 8) / 13))


def cutoff(hertz: float) -> float:
    """A filter cutoff: 130 semitones centred a little above A440."""
    return min(1.0, max(0.0, (12 * math.log2(hertz / 440) + 60) / 130))


def gain(decibels: float) -> float:
    """ "A VCA Gain" and "A Pre-Filter Gain": 96 dB across the range, 0 dB in the middle."""
    return min(1.0, max(0.0, 0.5 + decibels / 96))


def level(decibels: float) -> float:
    """Oscillator and scene volumes, which are cubic: 1.0 is 0 dB."""
    return min(1.0, max(0.0, 10 ** (decibels / 60)))


def filter_env(semitones: float) -> float:
    """ "A Filter 1 FEG Mod Amount": 192 semitones across the range."""
    return min(1.0, max(0.0, 0.5 + semitones / 192))


def fm_ratio(ratio: float) -> float:
    """An FM2 modulator ratio ("C : 7"), which runs from 1 at 0 to 33 at 1."""
    return min(1.0, max(0.0, (ratio - 1) / 32))


def detune(cents: float) -> float:
    """Unison detune, where 1.0 is 100 cents."""
    return min(1.0, max(0.0, cents / 100))


_BASE = {
    "Global Volume": 1.0,
    "A Volume": 1.0,
    "A Pre-Filter Gain": 0.5,
    "A VCA Gain": 0.5,
}


def surge(name: str = "synth", *patches: dict[str, float], **params: float) -> Device:
    """A Surge XT device from one or more patches, later ones winning."""
    merged = dict(_BASE)
    for patch in patches:
        merged.update(patch)
    merged.update({k.replace("_", " "): v for k, v in params.items()})
    return Device(name=name, identifier=SURGE_XT, params=merged)


def amp(attack: float, decay: float, sustain: float, release: float) -> dict[str, float]:
    """An amplitude envelope, in seconds."""
    return {
        "A Amp EG Attack": seconds(attack) if attack > 0 else 0.0,
        "A Amp EG Decay": seconds(decay),
        "A Amp EG Sustain": sustain,
        "A Amp EG Release": seconds(release),
    }


def filter_eg(attack: float, decay: float, sustain: float, release: float) -> dict[str, float]:
    """The filter envelope, in seconds."""
    return {
        "A Filter EG Attack": seconds(attack) if attack > 0 else 0.0,
        "A Filter EG Decay": seconds(decay),
        "A Filter EG Sustain": sustain,
        "A Filter EG Release": seconds(release),
    }


# -----------------------------------------------------------------------------
# Drums
#
# Host parameters cannot reach Surge's modulation matrix, so nothing can sweep an
# oscillator's pitch. The kick gets its drop the way analog drum machines do, from
# a resonant filter ringing as its envelope falls: measured 356 Hz to 52 Hz in 36 ms.
# -----------------------------------------------------------------------------


def kick() -> dict[str, float]:
    """Play at MIDI 31 (G1), which is where the filter comes to rest."""
    return {
        "A Osc 1 Type": OSC["sine"],
        "A Osc 1 Volume": 0.75,
        "A Filter 1 Type": FILTER["ladder"],
        "A Filter 1 Cutoff": cutoff(50),
        "A Filter 1 Resonance": 0.97,
        "A Filter 1 FEG Mod Amount": 0.82,
        "A VCA Gain": 0.66,
        **filter_eg(0, 0.045, 0.0, 0.04),
        **amp(0, 0.22, 0.0, 0.08),
    }


def snare() -> dict[str, float]:
    """A sine body under filtered noise. Play at MIDI 55."""
    return {
        "A Osc 1 Type": OSC["sine"],
        "A Osc 1 Volume": 0.7,
        "A Noise Mute": 0.0,
        "A Noise Volume": 0.95,
        "A Noise Color": 0.55,
        "A Filter 1 Type": FILTER["hp12"],
        "A Filter 1 Cutoff": cutoff(180),
        "A VCA Gain": 0.61,
        **amp(0, 0.13, 0.0, 0.06),
    }


def clap() -> dict[str, float]:
    """Band-passed noise. Play at MIDI 55."""
    return {
        "A Osc 1 Mute": 1.0,
        "A Noise Mute": 0.0,
        "A Noise Volume": 1.0,
        "A Noise Color": 0.6,
        "A Filter 1 Type": FILTER["bp12"],
        "A Filter 1 Cutoff": cutoff(1400),
        "A Filter 1 Resonance": 0.25,
        "A VCA Gain": 0.86,
        **amp(0, 0.16, 0.0, 0.1),
    }


def hat(decay: float = 0.045) -> dict[str, float]:
    """High-passed noise. Pass a longer decay for an open hat."""
    return {
        "A Osc 1 Mute": 1.0,
        "A Noise Mute": 0.0,
        "A Noise Volume": 1.0,
        "A Noise Color": 0.8,
        "A Filter 1 Type": FILTER["hp24"],
        "A Filter 1 Cutoff": cutoff(6500),
        "A VCA Gain": 0.68,
        **amp(0, decay, 0.0, 0.03),
    }


def ride() -> dict[str, float]:
    """Two square waves ring-modulated at an inharmonic ratio, as an 808 does. Play at MIDI 84."""
    return {
        "A Osc 1 Type": OSC["classic"],
        "A Osc 2 Type": OSC["classic"],
        "A Osc 1 Shape": 1.0,
        "A Osc 2 Shape": 1.0,
        "A Osc 1 Mute": 1.0,
        "A Osc 2 Mute": 1.0,
        "A Osc 2 Pitch": 0.62,
        "A Ring Modulation 1x2 Mute": 0.0,
        "A Ring Modulation 1x2 Volume": 1.0,
        "A Noise Mute": 0.0,
        "A Noise Volume": 0.5,
        "A Noise Color": 0.8,
        "A Filter 1 Type": FILTER["hp24"],
        "A Filter 1 Cutoff": cutoff(3500),
        "A VCA Gain": 0.58,
        **amp(0, 0.9, 0.0, 0.5),
    }


def impact() -> dict[str, float]:
    """A long noise burst for the top of a drop."""
    return {
        "A Osc 1 Mute": 1.0,
        "A Noise Mute": 0.0,
        "A Noise Volume": 1.0,
        "A Noise Color": 0.6,
        "A Filter 1 Type": FILTER["hp12"],
        "A Filter 1 Cutoff": cutoff(400),
        "A VCA Gain": 0.52,
        **amp(0, 2.2, 0.0, 0.8),
    }


def riser() -> dict[str, float]:
    """Noise through a low-pass. Automate "A Filter 1 Cutoff" to make it rise."""
    return {
        "A Osc 1 Mute": 1.0,
        "A Noise Mute": 0.0,
        "A Noise Volume": 1.0,
        "A Noise Color": 0.5,
        "A Filter 1 Type": FILTER["lp24"],
        "A Filter 1 Cutoff": cutoff(300),
        "A Filter 1 Resonance": 0.45,
        "A VCA Gain": 0.5,
        **amp(0.05, 1.0, 1.0, 0.3),
    }


# -----------------------------------------------------------------------------
# Keys and bass
# -----------------------------------------------------------------------------


def electric_piano() -> dict[str, float]:
    """FM tine through a filter whose envelope supplies the bark of the attack."""
    return {
        "A Osc 1 Type": OSC["fm2"],
        "A Osc 1 Shape": 0.2,
        "A Osc 1 Width 1": fm_ratio(1),
        "A Osc 1 Width 2": 0.18,
        "A Osc 1 Sub Mix": fm_ratio(14),
        "A Filter 1 Type": FILTER["lp12"],
        "A Filter 1 Cutoff": cutoff(1500),
        "A Filter 1 FEG Mod Amount": filter_env(30),
        "A VCA Gain": gain(-12),
        **filter_eg(0, 0.32, 0.2, 0.3),
        **amp(0.003, 1.6, 0.25, 0.25),
    }


def electric_bass() -> dict[str, float]:
    """A round, plucked electric bass."""
    return {
        "A Osc 1 Type": OSC["classic"],
        "A Osc 1 Shape": 0.5,
        "A Osc 1 Sub Mix": 0.3,
        "A Filter 1 Type": FILTER["lp24"],
        "A Filter 1 Cutoff": cutoff(420),
        "A Filter 1 Resonance": 0.15,
        "A Filter 1 FEG Mod Amount": filter_env(24),
        "A VCA Gain": gain(10),
        **filter_eg(0, 0.18, 0.15, 0.1),
        **amp(0.002, 0.7, 0.55, 0.08),
    }


def sub_bass() -> dict[str, float]:
    """A plain sine, for under a big chord."""
    return {
        "A Osc 1 Type": OSC["sine"],
        "A VCA Gain": gain(-2),
        **amp(0.004, 1.0, 1.0, 0.06),
    }


# -----------------------------------------------------------------------------
# Leads, pads and chords
# -----------------------------------------------------------------------------


def mono_lead() -> dict[str, float]:
    """A warm saw lead that glides, in the Moog tradition."""
    return {
        "A Osc 1 Type": OSC["classic"],
        "A Osc 2 Type": OSC["classic"],
        "A Osc 1 Shape": 0.5,
        "A Osc 2 Shape": 0.5,
        "A Osc 2 Mute": 0.0,
        "A Osc 2 Pitch": 0.503,
        "A Filter 1 Type": FILTER["ladder"],
        "A Filter 1 Cutoff": cutoff(1600),
        "A Filter 1 Resonance": 0.28,
        "A Filter 1 FEG Mod Amount": filter_env(18),
        "A Play Mode": PLAY_MODE["mono"],
        "A Portamento": seconds(0.03),
        "A VCA Gain": gain(10),
        **filter_eg(0.004, 0.35, 0.35, 0.2),
        **amp(0.006, 0.5, 0.85, 0.12),
    }


def warm_pad() -> dict[str, float]:
    """Slow, soft, detuned saws."""
    return {
        "A Osc 1 Type": OSC["classic"],
        "A Osc 1 Shape": 0.5,
        "A Osc 1 Unison Voices": UNISON[3],
        "A Osc 1 Unison Detune": detune(12),
        "Polyphony Limit": 0.9,
        "A Filter 1 Type": FILTER["lp12"],
        "A Filter 1 Cutoff": cutoff(1300),
        "A VCA Gain": gain(-11),
        **amp(0.5, 1.0, 1.0, 1.2),
    }


def supersaw() -> dict[str, float]:
    """The big unison saw stack that future bass chords are made of."""
    return {
        "A Osc 1 Type": OSC["classic"],
        "A Osc 2 Type": OSC["classic"],
        "A Osc 1 Shape": 0.5,
        "A Osc 2 Shape": 0.5,
        "A Osc 2 Mute": 0.0,
        "A Osc 1 Unison Voices": UNISON[7],
        "A Osc 2 Unison Voices": UNISON[5],
        "A Osc 1 Unison Detune": detune(22),
        "A Osc 2 Unison Detune": detune(15),
        "Polyphony Limit": 0.9,
        "A Filter 1 Type": FILTER["lp24"],
        "A Filter 1 Cutoff": cutoff(9000),
        "A VCA Gain": gain(-2),
        **amp(0.003, 0.6, 1.0, 0.18),
    }


def pluck() -> dict[str, float]:
    """A short, bright pluck for arpeggios."""
    return {
        "A Osc 1 Type": OSC["classic"],
        "A Osc 1 Shape": 0.5,
        "A Filter 1 Type": FILTER["lp24"],
        "A Filter 1 Cutoff": cutoff(500),
        "A Filter 1 FEG Mod Amount": filter_env(55),
        "A VCA Gain": gain(-12),
        **filter_eg(0, 0.14, 0.0, 0.1),
        **amp(0.002, 0.22, 0.0, 0.14),
    }


def chop() -> dict[str, float]:
    """A vowel-like lead, for lines that stand in for a vocal chop."""
    return {
        "A Osc 1 Type": OSC["classic"],
        "A Osc 1 Shape": 0.5,
        "A Filter 1 Type": FILTER["bp12"],
        "A Filter 1 Cutoff": cutoff(1500),
        "A Filter 1 Resonance": 0.55,
        "A Filter 1 Keytrack": 0.62,
        "A VCA Gain": gain(14),
        **amp(0.004, 0.2, 0.55, 0.09),
    }
