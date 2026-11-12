"""
Build the sampled instruments the example songs play, from their CC0 sources.

The tables in `pypulang/sounds/instruments.py` say which samples each instrument
uses and the note each one sounds. This fetches them from the two libraries'
GitHub repositories, keeps the first seconds of each (only those bytes are
downloaded), trims the silence before the attack, evens out the levels within each
library folder, and writes `<out>/<instrument>/<root>.wav`.

    python scripts/get_instrument_samples.py [--only piano,strings] [--out DIR]

About 700 MB is downloaded for all ten instruments and their layers, and 260 MB
written. Needs numpy
and soundfile.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf

from pypulang.sounds.instruments import INSTRUMENTS, Instrument, Source

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "examples" / "songs" / "samples" / "instruments"
RAW = "https://raw.githubusercontent.com/sgossner/{repo}/master/{path}"
TREE = "https://api.github.com/repos/sgossner/{repo}/git/trees/master?recursive=1"
PITCH_CLASSES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

SOURCES = """# Sampled instruments for the example songs

Built by `scripts/get_instrument_samples.py`; not in the repository. Each folder
holds one sample per root note, named by its MIDI note.

| Library | Instruments | License |
|---|---|---|
| [Versilian Community Sample Library](https://github.com/sgossner/VCSL) | piano (Steinway B), tenor_sax, vibes | CC0 1.0 |
| [VSCO 2 Community Edition](https://github.com/sgossner/VSCO-2-CE) | upright_bass, muted_trumpet, trumpet, trumpet_stab, trombone, trombone_stab, strings | CC0 1.0 |
"""


def midi_of(name: str, octave: int) -> int:
    m = re.fullmatch(r"([A-G])(#?)(-?\d)", name)
    if m is None:
        raise ValueError(f"not a note name: {name}")
    return (int(m[3]) + octave + 1) * 12 + PITCH_CLASSES[m[1]] + (1 if m[2] else 0)


def files_of(source: Source, tree: list[dict]) -> dict[int, str]:
    """Root note to the library path of its sample."""
    found: dict[int, str] = {}
    for entry in tree:
        path = entry["path"]
        folder, _, name = path.rpartition("/")
        if entry["type"] != "blob" or folder != source.folder:
            continue
        m = re.search(source.pattern, name)
        if m:
            found.setdefault(midi_of(m[1], source.octave), path)
    missing = sorted(set(source.roots) - set(found))
    if missing:
        raise FileNotFoundError(f"{source.folder}: no sample for notes {missing}")
    return {root: found[root] for root in source.roots}


def fetch(url: str, start: int, end: int) -> bytes:
    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end - 1}"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def read_start(repo: str, path: str, seconds: float) -> tuple[np.ndarray, int]:
    """The first `seconds` of a WAV file, fetching only those bytes."""
    url = RAW.format(repo=repo, path=urllib.parse.quote(path))
    head = fetch(url, 0, 1 << 16)
    if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        raise ValueError(f"{path} is not a WAV file")
    pos, fmt = 12, None
    while pos + 8 <= len(head):
        chunk, size = head[pos : pos + 4], struct.unpack("<I", head[pos + 4 : pos + 8])[0]
        if chunk == b"fmt ":
            tag, channels, rate, _, _, bits = struct.unpack("<HHIIHH", head[pos + 8 : pos + 24])
            if tag == 0xFFFE:  # WAVE_FORMAT_EXTENSIBLE: the real tag is in the GUID
                tag = struct.unpack("<H", head[pos + 32 : pos + 34])[0]
            fmt = (tag, channels, rate, bits)
        elif chunk == b"data":
            break
        pos += 8 + size + (size & 1)
    else:
        raise ValueError(f"{path}: no data chunk in its first 64 KB")
    tag, channels, rate, bits = fmt
    frame = channels * bits // 8
    begin = pos + 8
    wanted = min(size, int(seconds * rate) * frame)
    body = fetch(url, begin, begin + wanted)
    body = body[: len(body) // frame * frame]
    if tag == 3:
        audio = np.frombuffer(body, dtype=f"<f{bits // 8}").astype(np.float64)
    elif bits == 24:
        b = np.frombuffer(body, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        audio = np.where(v >= 1 << 23, v - (1 << 24), v) / float(1 << 23)
    else:
        audio = np.frombuffer(body, dtype=f"<i{bits // 8}") / float(1 << (bits - 1))
    audio = audio.reshape(-1, channels)
    if channels == 1:
        audio = np.repeat(audio, 2, axis=1)
    return audio, rate


def trimmed(audio: np.ndarray, rate: int, seconds: float) -> np.ndarray:
    """From just before the attack, `seconds` long, with its tail faded out."""
    level = np.max(np.abs(audio), axis=1)
    onset = int(np.argmax(level > level.max() * 0.02))
    audio = audio[max(0, onset - int(0.003 * rate)) :][: int(seconds * rate)].copy()
    fade = min(len(audio) // 4, int(0.4 * rate))
    if fade:
        audio[-fade:] *= np.cos(np.linspace(0, np.pi / 2, fade))[:, None] ** 2
    return audio


def loudness(audio: np.ndarray, rate: int) -> float:
    """RMS of the first half second: the attack and the start of the sustain."""
    return float(np.sqrt(np.mean(audio[: rate // 2] ** 2)) + 1e-9)


def build(name: str, spec: Instrument, trees: dict[str, list[dict]], out: Path) -> str:
    """
    Every layer of an instrument: the main one in `<out>/<name>`, others below it.

    Each folder of samples is levelled to one loudness, so a layer differs from
    another in tone and velocity sets the level. The main layer's loudest peak
    goes to -1 dBFS, as it did before instruments had layers, so songs balanced
    then keep their balance; the other layers take the same gain, less if it
    would clip them, so a softly played layer can end up a little quieter.
    """
    layers = {out / name: read_layer(spec.sources, spec.seconds, trees)}
    for layer in spec.layers:
        layers[out / name / layer.name] = read_layer(layer.sources, spec.seconds, trees)

    def headroom(samples: dict[int, tuple[np.ndarray, int]]) -> float:
        return 10 ** (-1 / 20) / max(float(np.max(np.abs(a))) for a, _ in samples.values())

    gain = headroom(layers[out / name])
    for folder, samples in layers.items():
        folder.mkdir(parents=True, exist_ok=True)
        level = min(gain, headroom(samples))
        for root, (audio, rate) in samples.items():
            sf.write(folder / f"{root}.wav", audio * level, rate, subtype="PCM_16")
    return f"{name}: " + ", ".join(
        f"{folder.relative_to(out)} {len(samples)} samples" for folder, samples in layers.items()
    )


def read_layer(
    sources: tuple[Source, ...], seconds: float, trees: dict[str, list[dict]]
) -> dict[int, tuple[np.ndarray, int]]:
    """One layer's samples by root, each folder brought to one median loudness."""
    samples: dict[int, tuple[np.ndarray, int]] = {}
    for source in sources:
        paths = files_of(source, trees[source.repo])
        with ThreadPoolExecutor(6) as pool:
            fetched = pool.map(
                read_start,
                [source.repo] * len(paths),
                paths.values(),
                [seconds + 0.5] * len(paths),
            )
            read = dict(zip(paths, fetched, strict=True))
        # One gain per folder, bringing its median loudness to a common level, so
        # the strings' three sections join without a step and each folder keeps
        # its own rise and fall across the range.
        cut = {root: (trimmed(a, r, seconds), r) for root, (a, r) in read.items()}
        median = float(np.median([loudness(a, r) for a, r in cut.values()]))
        for root, (audio, rate) in cut.items():
            samples[root] = (audio * (0.1 / median), rate)
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--only", help="Comma-separated instruments (default all)")
    parser.add_argument("--out", default=str(OUT), help="Where the instruments go")
    args = parser.parse_args()
    out = Path(args.out)
    names = args.only.split(",") if args.only else list(INSTRUMENTS)
    for name in names:
        if name not in INSTRUMENTS:
            raise SystemExit(f"No instrument {name!r}; there are {', '.join(INSTRUMENTS)}")
    trees = {}
    for repo in {s.repo for n in names for s in INSTRUMENTS[n].sources}:
        with urllib.request.urlopen(TREE.format(repo=repo), timeout=120) as response:
            trees[repo] = json.load(response)["tree"]
    for name in names:
        print(build(name, INSTRUMENTS[name], trees, out), flush=True)
    out.mkdir(parents=True, exist_ok=True)
    (out / "SOURCES.md").write_text(SOURCES)


if __name__ == "__main__":
    main()
