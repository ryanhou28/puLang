"""
Variations: alternatives for one place in a song, proposed and picked.

A variation is a named bundle of edits above the notes (see
`pypulang.compiler.edits`) at a site, such as "chorus hook" or "verse harmony".
Anyone can propose one, a person or an agent; the song's source is always the
first alternative at every site. Picking one records the choice in the song's
overrides, beside the hand edits, and every compile applies the chosen bundles
before the hand edits, so a hand edit still has the last word.

    pulang propose song.py "chorus hook" hook-b intent:motif/hook:notes="3/4 2/8 1 ..."
    pulang variations song.py
    pulang pick song.py hook-b

A bundle is checked by compiling the song with it before it is kept, and is
described by what it does to the notes: which section occurrences and parts
change, and how many notes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pypulang.compiler.edits import Edit

if TYPE_CHECKING:
    from pypulang.backends.kaidaw.state import Overrides
    from pypulang.compiler.pipeline import CompileResult

SOURCE = "source"


@dataclass
class Variation:
    name: str
    site: str
    edits: list[Edit]
    description: str = ""
    author: str = ""
    created: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "site": self.site,
            "edits": [e.to_json() for e in self.edits],
            "description": self.description,
            "author": self.author,
            "created": self.created,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Variation:
        return cls(
            data["name"],
            data["site"],
            [Edit.from_json(e) for e in data.get("edits", [])],
            data.get("description", ""),
            data.get("author", ""),
            data.get("created", ""),
        )


def sites(overrides: Overrides) -> dict[str, list[Variation]]:
    """Each site and its proposed variations, in the order they were proposed."""
    found: dict[str, list[Variation]] = defaultdict(list)
    for data in overrides.variations.values():
        variation = Variation.from_json(data)
        found[variation.site].append(variation)
    return dict(found)


def chosen(overrides: Overrides) -> list[Variation]:
    """The variations picked, one per site at most."""
    return [
        Variation.from_json(overrides.variations[name])
        for name in overrides.choices.values()
        if name in overrides.variations
    ]


def song_edits(
    overrides: Overrides, trying: Variation | None = None, site: str | None = None
) -> list[Edit]:
    """
    The edits a compile applies: the chosen variations', then the hand edits.

    Args:
        trying: Apply this variation at its site instead of the one chosen there
        site: With `trying` None, play the source at this site instead of its choice
    """
    replaced = trying.site if trying is not None else site
    edits: list[Edit] = []
    for variation in chosen(overrides):
        if variation.site != replaced:
            edits.extend(variation.edits)
    if trying is not None:
        edits.extend(trying.edits)
    return [*edits, *overrides.edit_list()]


@dataclass
class Effect:
    """What a change does to the notes, by section occurrence and part."""

    changed: dict[str, int] = field(default_factory=dict)  # "chorus#1/lead" -> notes
    added: dict[str, int] = field(default_factory=dict)
    removed: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.changed.values()) + sum(self.added.values()) + sum(self.removed.values())

    def places(self) -> list[str]:
        return sorted({*self.changed, *self.added, *self.removed})

    def summary(self) -> str:
        if not self.total:
            return "changes no notes"
        parts = []
        for place in self.places():
            counts = [
                f"{n} {what}"
                for what, n in (
                    ("changed", self.changed.get(place, 0)),
                    ("added", self.added.get(place, 0)),
                    ("removed", self.removed.get(place, 0)),
                )
                if n
            ]
            parts.append(f"{place} ({', '.join(counts)})")
        return "; ".join(parts)

    def to_json(self) -> dict[str, Any]:
        return {"total": self.total, "summary": self.summary(), "places": self.places()}


def effect(before: CompileResult, after: CompileResult) -> Effect:
    """Compare the notes of two compiles of one song."""
    from pypulang.lift import daw_notes

    old, new = daw_notes(before.daw), daw_notes(after.daw)
    result = Effect()

    def place(loc: str) -> str:
        tag, _, rest = loc.partition("/")
        return f"{tag}/{rest.partition('/')[0]}"

    def bump(table: dict[str, int], loc: str) -> None:
        table[place(loc)] = table.get(place(loc), 0) + 1

    for loc, note in new.items():
        if loc not in old:
            bump(result.added, loc)
        elif old[loc] != note:
            bump(result.changed, loc)
    for loc in old:
        if loc not in new:
            bump(result.removed, loc)
    return result


def focus(effects: list[Effect], order: list[str]) -> str | None:
    """
    The section occurrence to hear a set of alternatives in: the first, in `order`,
    where they change at least half as many notes as where they change the most.

    A chorus hook teased once in the intro is heard in the first chorus, not the
    intro, because the intro changes only a few notes.
    """
    counts: dict[str, int] = defaultdict(int)
    for one in effects:
        for table in (one.changed, one.added, one.removed):
            for place, n in table.items():
                counts[place.partition("/")[0]] += n
    if not counts:
        return None
    enough = max(counts.values()) / 2
    return next((tag for tag in order if counts.get(tag, 0) >= enough), None)
