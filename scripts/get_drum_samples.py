"""
Build the drum kits the example songs play, from their sources.

The samples are not in this repository. Two of the three sources are CC0 and
could be, but the TR-909 hits are only free to use, not to redistribute, so the
kits are built here from where each source publishes them:

    jazz/    Virtuosity Drums by Versilian Studios, CC0. A contemporary jazz kit
             recorded on six mics; each hit here is its close mic, overheads and
             room mixed into one stereo file, as a kit mixer would.
    future/  Kickmess kicks from the Meadowlark factory library, CC0, and TR-909
             hits by F9 Audio, free to use (mirrored by oramics/sampled).

Virtuosity Drums is a 1.2 GB zip; only the dozen files a kit needs are read from
it, with HTTP range requests, unless a local copy is given with --zip.

    python scripts/get_drum_samples.py [--zip Virtuosity_Drums_v0.925.zip]

Needs numpy and soundfile.
"""

from __future__ import annotations

import argparse
import io
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "examples" / "songs" / "samples"
VIRTUOSITY = "https://versilian-studios.com/Distro/Virtuosity_Drums_v0.925.zip"
TR909 = "https://raw.githubusercontent.com/oramics/sampled/master/DM/TR-909/Detroit/samples/"
MEADOWLARK = "https://raw.githubusercontent.com/BillyDM/meadowlark-factory-library/main/"

# Each jazz hit: the folder and articulation in the archive, which layer (0 the
# softest, 1 the loudest), the mics mixed with their gains, and optionally how many
# seconds to keep before a fade.
JAZZ = {
    "kick.wav": ("kick", "kick_snon", 0.75, {"kickmic": 1.0, "oh": 0.45, "room": 0.3}, 0.8),
    "snare.wav": ("snare", "snare_center", 0.75, {"snaremic": 1.0, "oh": 0.55, "room": 0.3}),
    "cross-stick.wav": (
        "snare",
        "snare_crossstick",
        0.7,
        {"snaremic": 1.0, "oh": 0.5, "room": 0.25},
    ),
    "hihat-closed.wav": ("hh", "hh_closed", 0.6, {"oh": 1.0, "snaremic": 0.2, "room": 0.2}),
    "hihat-open.wav": ("hh", "hh_open", 0.6, {"oh": 1.0, "snaremic": 0.2, "room": 0.25}),
    "hihat-pedal.wav": ("hh", "hh_pedal", 0.6, {"oh": 1.0, "snaremic": 0.2, "room": 0.2}),
    "ride.wav": ("ride", "ride_ride", 0.6, {"oh": 1.0, "room": 0.3}),
    "ride-bell.wav": ("ride", "ride_bell", 0.6, {"oh": 1.0, "room": 0.3}),
    "crash.wav": ("crash", "crash_crash", 0.7, {"oh": 1.0, "room": 0.35}),
    "tom-high.wav": ("htom", "htom_center", 0.7, {"oh": 1.0, "room": 0.35}),
    "tom-low.wav": ("ltom", "ltom_center", 0.7, {"oh": 1.0, "room": 0.35}),
}

FUTURE = {
    "kick.wav": MEADOWLARK + "Drums - One Shot/Kicks/Snappy/Kickmess Snappy 4.wav",
    "kick-deep.wav": MEADOWLARK + "Drums - One Shot/Kicks/Deep/Kickmess Deep 4.wav",
    "clap.wav": TR909 + "clap-1.wav",
    "snare.wav": TR909 + "snare.wav",
    "hihat-closed.wav": TR909 + "hihat-closed.wav",
    "hihat-open.wav": TR909 + "hihat-open-1.wav",
    "crash.wav": TR909 + "cymbal.wav",
}

SOURCES = """# Drum samples for the example songs

Built by `scripts/get_drum_samples.py`; not in the repository.

| Kit | Source | License |
|---|---|---|
| jazz/ | [Virtuosity Drums](https://versilian-studios.com/virtuosity-drums/), Versilian Studios | CC0 1.0 |
| future/kick*.wav | Kickmess kicks, [Meadowlark factory library](https://github.com/BillyDM/meadowlark-factory-library) | CC0 1.0 |
| future/ (the rest) | TR-909 Detroit kit by F9 Audio, via [oramics/sampled](https://github.com/oramics/sampled/tree/master/DM/TR-909/Detroit) | Free to use; not for redistribution |
"""


class HttpRangeFile(io.RawIOBase):
    """A remote file read with HTTP Range requests, so zipfile can open it in place."""

    def __init__(self, url: str):
        head = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"))
        self.url, self.size, self.pos = url, int(head.headers["content-length"]), 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def readinto(self, buffer) -> int:  # noqa: ANN001 — io's own signature
        n = min(len(buffer), self.size - self.pos)
        if n <= 0:
            return 0
        request = urllib.request.Request(
            self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"}
        )
        data = urllib.request.urlopen(request).read()
        buffer[: len(data)] = data
        self.pos += len(data)
        return len(data)


def layer_file(names: list[str], mic: str, folder: str, articulation: str, where: float) -> str:
    """The layer `where` of the way up, for one mic; its first round robin if it has several."""
    pattern = re.compile(rf"^Samples/{mic}/{folder}/{mic}_{articulation}_vl(\d+)(?:_rr1)?\.flac$")
    layers = sorted((int(m[1]), n) for n in names if (m := pattern.match(n)))
    if not layers:
        raise FileNotFoundError(f"{mic}/{folder}/{articulation} is not in the archive")
    return layers[min(len(layers) - 1, round(where * (len(layers) - 1)))][1]


def mixed(
    archive: zipfile.ZipFile, folder: str, articulation: str, where: float, mics: dict
) -> tuple:
    """One hit on several mics, summed, trimmed of trailing silence, peaking at -1 dBFS."""
    names = archive.namelist()
    total, rate = None, None
    for mic, gain in mics.items():
        audio, rate = sf.read(
            io.BytesIO(archive.read(layer_file(names, mic, folder, articulation, where))),
            always_2d=True,
        )
        if audio.shape[1] == 1:
            audio = np.repeat(audio, 2, axis=1)
        if total is None:
            total = np.zeros_like(audio)
        n = min(len(total), len(audio))
        total = total[:n] + gain * audio[:n]
    loud = np.nonzero(np.max(np.abs(total), axis=1) > 10 ** (-70 / 20))[0]
    total = total[: loud[-1] + 1 if len(loud) else len(total)]
    return total * (10 ** (-1 / 20) / np.max(np.abs(total))), rate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--zip", help="A local copy of Virtuosity_Drums_v0.925.zip")
    parser.add_argument("--out", default=str(OUT), help="Where the kits go")
    args = parser.parse_args()
    out = Path(args.out)

    source = (
        Path(args.zip).open("rb")
        if args.zip
        else io.BufferedReader(HttpRangeFile(VIRTUOSITY), 1 << 16)
    )
    with zipfile.ZipFile(source) as archive:
        (out / "jazz").mkdir(parents=True, exist_ok=True)
        for name, (folder, articulation, where, mics, *rest) in JAZZ.items():
            audio, rate = mixed(archive, folder, articulation, where, mics)
            if rest:
                # The room mic rings for two seconds; under a busy pattern the tails
                # pile up into low-end rumble, so this one fades out early.
                keep, fade = int(rest[0] * rate), int(0.25 * rate)
                audio = audio[:keep].copy()
                audio[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None] ** 2
            sf.write(out / "jazz" / name, audio, rate, subtype="PCM_24")
            print(f"jazz/{name}: {len(audio) / rate:.2f} s")

    (out / "future").mkdir(parents=True, exist_ok=True)
    for name, url in FUTURE.items():
        data = urllib.request.urlopen(urllib.parse.quote(url, safe=":/")).read()
        # Peaking at -1 dBFS like the jazz kit; some 909 hits were recorded 15 dB down.
        audio, rate = sf.read(io.BytesIO(data), always_2d=True)
        sf.write(
            out / "future" / name,
            audio * (10 ** (-1 / 20) / np.max(np.abs(audio))),
            rate,
            subtype="PCM_24",
        )
        print(f"future/{name}: {len(audio) / rate:.2f} s")
    (out / "SOURCES.md").write_text(SOURCES)


if __name__ == "__main__":
    main()
