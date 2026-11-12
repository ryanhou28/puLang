"""
Acoustic instruments, sampled: piano, upright bass, brass, saxophone, strings, vibes.

Each is a zone map for kaiDAW's sampler, built from two CC0 libraries by Sam
Gossner and contributors: the Versilian Community Sample Library (VCSL) and the
Versilian Studios Chamber Orchestra 2 Community Edition (VSCO-2-CE). The samples
are not in this repository; `scripts/get_instrument_samples.py` builds them into
`<folder>/<instrument>/<root>.wav`, one file per root note, from these tables.

The sampler plays one sample per key range and follows velocity with gain alone,
so each instrument here is one dynamic layer of its library, chosen for a
mezzo-forte player. A note held longer than its sample runs out: sustained
sounds keep about six seconds.
"""

from __future__ import annotations

from dataclasses import dataclass

from pypulang.ir.intent import Device
from pypulang.sounds import sampler

VCSL = "VCSL"
VSCO = "VSCO-2-CE"


@dataclass(frozen=True)
class Source:
    """One folder of a library, and the samples taken from it."""

    repo: str
    folder: str
    pattern: str  # picks one layer and round robin; its group 1 is the note name
    octave: int  # added to the library's octave numbers: most name middle C "C3"
    roots: tuple[int, ...]  # the MIDI note each chosen sample sounds


@dataclass(frozen=True)
class Instrument:
    sources: tuple[Source, ...]
    seconds: float  # kept from the start of each sample
    one_shot: bool  # rings on after the note ends, as a struck or plucked sound does
    stretch: int = 4  # semitones the outermost samples are played beyond their roots

    def roots(self) -> list[int]:
        return sorted(r for s in self.sources for r in s.roots)


_NOTE = r"([A-G]#?-?\d)"

INSTRUMENTS: dict[str, Instrument] = {
    # A Steinway B, close mics, no pedal. Its file names count octaves the scientific way.
    "piano": Instrument(
        (
            Source(
                VCSL,
                "Chordophones/Zithers/Grand Piano, Steinway B/NoSus",
                rf"_NoSus_Close_{_NOTE}_vl3_rr1\.wav$",
                0,
                tuple(range(22, 105, 2)),
            ),
        ),
        seconds=8.0,
        one_shot=False,
    ),
    "upright_bass": Instrument(
        (
            Source(
                VSCO,
                "Strings/Solo Contrabass/Pizz",
                rf"_Pizz_{_NOTE}_v1_rr1\.wav$",
                1,
                (28, 30, 31, 34, 36, 38, 40, 42, 44, 45, 49, 52, 56, 59),
            ),
        ),
        seconds=3.0,
        one_shot=False,
    ),
    "vibes": Instrument(
        (
            Source(
                VCSL,
                "Idiophones/Struck Idiophones/Vibraphone/Soft Mallets",
                rf"_soft_{_NOTE}_v2_rr1_Main\.wav$",
                1,
                (53, 57, 60, 64, 67, 71, 74, 77, 81, 84, 88),
            ),
        ),
        seconds=6.0,
        one_shot=True,
    ),
    "muted_trumpet": Instrument(
        (
            Source(
                VSCO,
                "Brass/Trumpet/straightM-sus",
                rf"_straightM-sus_{_NOTE}_v3_rr1\.wav$",
                1,
                (58, 60, 62, 67, 70, 74, 77, 81),
            ),
        ),
        seconds=6.0,
        one_shot=False,
    ),
    "trumpet": Instrument(
        (
            Source(
                VSCO,
                "Brass/Trumpet/sus",
                rf"_sus_{_NOTE}_v3_rr1\.wav$",
                1,
                (53, 57, 60, 63, 67, 70, 74, 77, 81, 84),
            ),
        ),
        seconds=6.0,
        one_shot=False,
    ),
    "trumpet_stab": Instrument(
        (
            Source(
                VSCO,
                "Brass/Trumpet/stac",
                rf"_stac_{_NOTE}_v3_rr1\.wav$",
                1,
                (53, 57, 60, 63, 65, 67, 70, 74, 77, 81, 84),
            ),
        ),
        seconds=1.2,
        one_shot=True,
    ),
    "trombone": Instrument(
        (
            Source(
                VSCO,
                "Brass/Tenor Trombone/sus",
                rf"_sus_{_NOTE}_v2_1\.wav$",
                1,
                (34, 37, 39, 41, 46, 50, 53, 60, 61, 63, 65),
            ),
        ),
        seconds=6.0,
        one_shot=False,
    ),
    "trombone_stab": Instrument(
        (
            Source(
                VSCO,
                "Brass/Tenor Trombone/stac",
                rf"_stac_{_NOTE}_v3_rr1\.wav$",
                1,
                (34, 41, 46, 53, 58, 62, 65),
            ),
        ),
        seconds=1.2,
        one_shot=True,
    ),
    "tenor_sax": Instrument(
        (
            Source(
                VCSL,
                "Aerophones/Reed Aerophones/Tenor Saxophone/Non-Vibrato",
                rf"_NV_Main_{_NOTE}_vl2_rr1\.wav$",
                1,
                tuple(range(44, 89, 2)),
            ),
        ),
        seconds=6.0,
        one_shot=False,
    ),
    # A string section across its range: cellos at the bottom, violas in the middle,
    # violins on top, as an arranger would voice a pad.
    "strings": Instrument(
        (
            Source(
                VSCO,
                "Strings/Cello Section/susvib",
                rf"susvib_{_NOTE}_v3_1\.wav$",
                1,
                (36, 40, 43, 47, 50, 53),
            ),
            Source(
                VSCO,
                "Strings/Viola Section/susvib",
                rf"_susvib_{_NOTE}_v2_1\.wav$",
                1,
                (55, 59, 62, 65),
            ),
            Source(
                VSCO,
                "Strings/Violin Section/susVib",
                rf"_susVib_{_NOTE}_v2\.wav$",
                1,
                (69, 72, 76, 79, 83, 86),
            ),
        ),
        seconds=6.0,
        one_shot=False,
    ),
}


def zones(instrument: str) -> list[tuple[int, int, int]]:
    """(root, low, high) for each sample: each key plays the nearest root."""
    spec = INSTRUMENTS[instrument]
    roots = spec.roots()
    result = []
    for index, root in enumerate(roots):
        low = (roots[index - 1] + root) // 2 + 1 if index else max(0, root - spec.stretch)
        high = (root + roots[index + 1]) // 2 if index + 1 < len(roots) else root + spec.stretch
        result.append((root, low, min(high, 127)))
    return result


def sampled(
    name: str,
    instrument: str,
    folder: str = "samples/instruments",
    gain_db: float = 0.0,
    one_shot: bool | None = None,
) -> Device:
    """
    A sampled acoustic instrument on kaiDAW's sampler.

    Args:
        name: Local name, as for any device
        instrument: One of `INSTRUMENTS`: piano, upright_bass, vibes, muted_trumpet,
            trumpet, trumpet_stab, trombone, trombone_stab, tenor_sax, strings
        folder: Where `scripts/get_instrument_samples.py` put the samples, relative
            to the song
        gain_db: Gain of every sample
        one_shot: Override whether notes ring past their end

    Example:
        song.rack("piano", sampled("piano", "piano"), sends={"verb": 0.2})
    """
    if instrument not in INSTRUMENTS:
        raise ValueError(
            f"No sampled instrument {instrument!r}; there are {', '.join(INSTRUMENTS)}"
        )
    spec = INSTRUMENTS[instrument]
    ring = spec.one_shot if one_shot is None else one_shot
    return sampler(
        name,
        {
            root: {
                "file": f"{folder}/{instrument}/{root}.wav",
                "low": low,
                "high": high,
                "one_shot": ring,
            }
            for root, low, high in zones(instrument)
        },
        gain_db=gain_db,
    )
