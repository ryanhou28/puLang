"""
What puLang remembers about a song between pushes.

Two files live in `<song>.pulang/` beside the source:

`lock.json` is the source map. It records what was last pushed and which kaiDAW
object each piece of it became, keyed by source location.

`overrides.json` is part of the song. It holds the edits made in the DAW, and the
compiler applies them on every compile, so the notes a song produces are a pure
function of source plus overrides. Keep it in version control with the source.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Note = list[int]  # [pitch, start, duration, velocity], ticks from the clip start


@dataclass
class Lock:
    """The last push, and the kaiDAW id of everything in it."""

    tracks: dict[str, dict[str, Any]] = field(default_factory=dict)
    devices: dict[str, dict[str, Any]] = field(default_factory=dict)
    clips: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: dict[str, dict[str, Any]] = field(default_factory=dict)
    automations: dict[str, list[list[float]]] = field(default_factory=dict)
    sends: dict[str, float] = field(default_factory=dict)
    schemas: dict[str, dict[str, str]] = field(default_factory=dict)
    # Controller lanes last pushed, by "<clip key>/<controller>": [[tick, value], ...]
    controllers: dict[str, list[list[float]]] = field(default_factory=dict)

    def notes_in(self, clip_key: str) -> dict[str, dict[str, Any]]:
        return {loc: n for loc, n in self.notes.items() if n["clip"] == clip_key}

    @property
    def empty(self) -> bool:
        return not self.tracks


@dataclass
class Overrides:
    """
    Edits made in the DAW.

    `notes` maps a location to `{"note": [...], "base": [...]}` for an edit, or
    `{"deleted": true, "base": [...]}`. `base` is what the source produced when the
    edit was made, which is how a later compile notices the source moved underneath.

    `added` maps a clip to notes drawn by hand: `{"key": ..., "note": [...]}`.

    `clips` maps a clip to `{"deleted": true}`, or to any of `start`, `length`, and
    `track` for a clip moved or resized by hand.
    """

    notes: dict[str, dict[str, Any]] = field(default_factory=dict)
    added: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    clips: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.notes) + sum(len(v) for v in self.added.values()) + len(self.clips)


class SongState:
    """The `<song>.pulang/` directory."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    @classmethod
    def beside(cls, song: str | Path) -> SongState:
        path = Path(song)
        return cls(path.with_name(path.stem + ".pulang"))

    def _read(self, name: str) -> dict[str, Any]:
        path = self.directory / name
        return json.loads(path.read_text()) if path.exists() else {}

    def _write(self, name: str, data: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / name
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
        temporary.replace(path)

    def load_lock(self) -> Lock:
        return Lock(**self._read("lock.json"))

    def save_lock(self, lock: Lock) -> None:
        self._write("lock.json", lock.__dict__)

    def load_overrides(self) -> Overrides:
        return Overrides(**self._read("overrides.json"))

    def save_overrides(self, overrides: Overrides) -> None:
        self._write("overrides.json", overrides.__dict__)
