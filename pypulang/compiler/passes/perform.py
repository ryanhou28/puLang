"""
Performance passes on the `event` dialect.

These change when and how hard notes are played, and they run after the music is
settled. Each can be limited to named tracks and sections.

Humanizing draws its offsets from each note's own location. That makes it stable:
recompiling after a chord change leaves every other note exactly where it was, so
the DAW is not sent a thousand spurious edits.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from fractions import Fraction

from xdsl.context import Context
from xdsl.dialects.builtin import IntegerAttr, ModuleOp, i64
from xdsl.passes import ModulePass

from pypulang.compiler.dialects import event
from pypulang.compiler.dialects.mus import RationalAttr
from pypulang.compiler.locs import loc_key
from pypulang.compiler.passes.lower_event import PPQ


def _stream(module: ModuleOp) -> event.StreamOp:
    return next(o for o in module.body.block.ops if isinstance(o, event.StreamOp))


def _selected(
    module: ModuleOp, tracks: tuple[str, ...], sections: tuple[str, ...]
) -> list[event.NoteOp]:
    notes = []
    for track in _stream(module).tracks():
        if tracks and track.track.data not in tracks:
            continue
        for note in track.notes():
            if sections:
                tag = loc_key(note.location).partition("/")[0].partition("#")[0]
                if tag not in sections:
                    continue
            notes.append(note)
    return notes


def _set_time(note: event.NoteOp, start: Fraction, dur: Fraction) -> None:
    note.properties["start"] = RationalAttr(start)
    note.properties["dur"] = RationalAttr(dur)


def _set_velocity(note: event.NoteOp, velocity: int) -> None:
    note.properties["vel"] = IntegerAttr(max(1, min(127, velocity)), i64)


def swing_time(time: Fraction, ratio: Fraction, unit: Fraction) -> Fraction:
    """
    Warp a moment so the off-beat lands at `ratio` of the way through its pair.

    With an eighth-note unit of 1/2 and a ratio of 2/3, the second eighth of each
    beat moves from 1/2 to 2/3: triplet swing. On-beats do not move.
    """
    pair = unit * 2
    base = (time // pair) * pair
    within = (time - base) / pair
    half = Fraction(1, 2)
    if within <= half:
        warped = within * (ratio / half)
    else:
        warped = ratio + (within - half) * ((1 - ratio) / half)
    return base + warped * pair


@dataclass(frozen=True)
class Swing(ModulePass):
    """
    Delay the off-beats.

    Args:
        ratio: Where the off-beat lands, as a fraction of the pair. 1/2 is straight,
            2/3 is triplet swing. Written as a string such as "2/3".
        unit: Note value that swings, in beats (default "1/2", eighths)
        tracks: Only these tracks (default all)
        sections: Only these sections (default all)
    """

    name = "swing"
    ratio: str = "2/3"
    unit: str = "1/2"
    tracks: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        ratio = Fraction(self.ratio)
        unit = Fraction(self.unit)
        for note in _selected(op, self.tracks, self.sections):
            start = note.start.data
            end = start + note.dur.data
            new_start = swing_time(start, ratio, unit)
            new_end = swing_time(end, ratio, unit)
            _set_time(note, new_start, max(new_end - new_start, Fraction(1, PPQ)))


@dataclass(frozen=True)
class Humanize(ModulePass):
    """
    Small, repeatable imperfections in timing and velocity.

    Args:
        timing: Largest shift, in ticks of 1/960 of a beat (default 8)
        velocity: Largest velocity change (default 6)
        seed: Changes the whole performance while keeping it repeatable
        tracks: Only these tracks (default all)
        sections: Only these sections (default all)
    """

    name = "humanize"
    timing: int = 8
    velocity: int = 6
    seed: str = ""
    tracks: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        for note in _selected(op, self.tracks, self.sections):
            digest = hashlib.sha256(f"{self.seed}|{loc_key(note.location)}".encode()).digest()
            rng = random.Random(int.from_bytes(digest[:8], "big"))
            shift = Fraction(rng.randint(-self.timing, self.timing), PPQ)
            start = max(note.start.data + shift, Fraction(0))
            _set_time(note, start, note.dur.data)
            _set_velocity(note, note.vel.value.data + rng.randint(-self.velocity, self.velocity))


@dataclass(frozen=True)
class Accent(ModulePass):
    """
    Shape velocity by position in the beat.

    Args:
        on: Added to notes on the beat
        off: Added to everything else
        tracks: Only these tracks (default all)
        sections: Only these sections (default all)
    """

    name = "accent"
    on: int = 6
    off: int = -6
    tracks: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        for note in _selected(op, self.tracks, self.sections):
            on_beat = note.start.data.denominator == 1
            _set_velocity(note, note.vel.value.data + (self.on if on_beat else self.off))


@dataclass(frozen=True)
class Pump(ModulePass):
    """
    Duck a track's fader on every hit of another: the sidechain sound.

    kaiDAW has no sidechain routing, and this needs none. The ducking is a volume
    curve, computed from the trigger's notes, which is also how many producers do it.

    Args:
        target: Track to duck
        trigger: Track whose notes cause the ducks
        level: Fader value at rest (0.74 is unity)
        depth: How far it drops, as a portion of `level`
        release: Beats until it is back at rest
        sections: Only hits in these sections (default all)
    """

    name = "pump"
    target: str = ""
    trigger: str = ""
    level: float = 0.74
    depth: float = 0.7
    release: str = "3/4"
    sections: tuple[str, ...] = ()

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        stream = _stream(op)
        tracks = {t.track.data: t for t in stream.tracks()}
        release = Fraction(self.release)
        level = Fraction(self.level).limit_denominator(1000)
        low = level * (1 - Fraction(self.depth).limit_denominator(1000))
        attack = Fraction(1, 64)
        hits = sorted({n.start.data for n in _selected(op, (self.trigger,), self.sections)})
        points: list[tuple[Fraction, Fraction]] = []
        for index, hit in enumerate(hits):
            following = hits[index + 1] if index + 1 < len(hits) else hit + release
            gap = following - hit
            recover = min(release, gap - attack) if gap > attack else attack
            points.append((max(hit - attack, Fraction(0)), level))
            points.append((hit, low))
            # A fast start and a long tail, because a straight ramp sounds like a fade.
            points.append((hit + recover / 3, low + (level - low) * Fraction(2, 3)))
            points.append((hit + recover, level))
        if points:
            curve = event.CurveOp("mix.volume", points)
            tracks[self.target].body.block.add_op(curve)
