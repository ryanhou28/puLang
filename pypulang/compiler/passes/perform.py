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


@dataclass(frozen=True)
class Bend(ModulePass):
    """
    Pitch bends on a track's notes: a scoop up into a note, or a fall off its end.

    The bend is written to the track's pitch-bend lane, which every instrument
    hears and a person can redraw in the DAW. It suits a single line; on chords it
    bends every note at once, as a keyboard's wheel does.

    Args:
        track: Track to bend
        kind: "scoop" rises into the note from below; "fall" drops off its end
        semitones: How far the bend reaches
        time: How long it takes, in beats (default "1/8")
        min_length: Only notes at least this long, in beats (default "1/2")
        every: Every Nth such note, counting through the piece (default 1)
        bend_range: The instrument's bend range in semitones (Surge XT's default, 2)
        sections: Only notes in these sections (default all)
    """

    name = "bend"
    track: str = ""
    kind: str = "scoop"
    semitones: float = 1.0
    time: str = "1/8"
    min_length: str = "1/2"
    every: int = 1
    bend_range: float = 2.0
    sections: tuple[str, ...] = ()

    # Controllers hold until the next event, so a curve is drawn as steps.
    STEPS = 8

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        if self.kind not in ("scoop", "fall"):
            raise ValueError(f"bend kind must be 'scoop' or 'fall', not {self.kind!r}")
        track = next((t for t in _stream(op).tracks() if t.track.data == self.track), None)
        if track is None:
            raise ValueError(f"bend: no track {self.track!r}")
        time = Fraction(self.time)
        shortest = Fraction(self.min_length)
        depth = (
            Fraction(max(-1.0, min(1.0, self.semitones / self.bend_range))).limit_denominator(1000)
            / 2
        )
        notes = sorted(
            (n for n in _selected(op, (self.track,), self.sections) if n.dur.data >= shortest),
            key=lambda n: n.start.data,
        )
        points: list[tuple[Fraction, Fraction]] = []
        tick = Fraction(1, PPQ)
        for index, note in enumerate(notes):
            if index % max(1, self.every):
                continue
            start, end = note.start.data, note.start.data + note.dur.data
            if self.kind == "scoop":
                # Down a tick early, so the note starts bent rather than jumping
                # after its attack: a controller and a note on the same tick may
                # reach the instrument in either order.
                span = min(time, end - start)
                points.append((max(start - tick, Fraction(0)), Fraction(1, 2) - depth))
                for k in range(1, self.STEPS + 1):
                    eased = 1 - (1 - Fraction(k, self.STEPS)) ** 2
                    points.append(
                        (start + span * k / self.STEPS, Fraction(1, 2) - depth * (1 - eased))
                    )
            else:
                span = min(time, end - start)
                begin = end - span
                for k in range(self.STEPS + 1):
                    eased = Fraction(k, self.STEPS) ** 2
                    points.append((begin + span * k / self.STEPS, Fraction(1, 2) - depth * eased))
                points.append((end + tick, Fraction(1, 2)))
        if points:
            points.sort(key=lambda p: p[0])
            track.body.block.add_op(event.CurveOp("midi.pitchbend", points))


def _onsets(notes: list[event.NoteOp]) -> list[list[event.NoteOp]]:
    """Notes grouped by start time, in time order: a chord is one onset."""
    groups: dict[Fraction, list[event.NoteOp]] = {}
    for note in notes:
        groups.setdefault(note.start.data, []).append(note)
    return [groups[start] for start in sorted(groups)]


def _by_track(
    module: ModuleOp, tracks: tuple[str, ...], sections: tuple[str, ...]
) -> list[list[event.NoteOp]]:
    selected = {id(n) for n in _selected(module, tracks, sections)}
    return [
        [n for n in track.notes() if id(n) in selected]
        for track in _stream(module).tracks()
        if not tracks or track.track.data in tracks
    ]


@dataclass(frozen=True)
class LayBack(ModulePass):
    """
    Play a track a constant amount behind the beat, or ahead of it.

    Where each player sits against the beat is much of a band's feel: a bass on the
    beat and a singer a little behind it sounds unhurried, a drummer ahead of it
    sounds urgent. Run it after `Swing`, so the swung notes move together.

    Args:
        ticks: How far behind, in 1/960 of a beat; negative plays ahead (default 20)
        tracks: Only these tracks (default all)
        sections: Only these sections (default all)
    """

    name = "lay-back"
    ticks: int = 20
    tracks: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        shift = Fraction(self.ticks, PPQ)
        for note in _selected(op, self.tracks, self.sections):
            _set_time(note, max(note.start.data + shift, Fraction(0)), note.dur.data)


@dataclass(frozen=True)
class Phrasing(ModulePass):
    """
    Shape a line's dynamics by phrase, the way a player breathes.

    A rest of at least `gap` beats ends a phrase. Across each phrase the velocity
    rises to its highest note and falls away after it, and its last note is
    softer still, so a phrase arrives somewhere and lets go rather than being
    played at one level throughout.

    Args:
        depth: The difference in velocity between a phrase's peak and its ends (default 14)
        ending: Taken off a phrase's last note on top of that (default 8)
        gap: A rest at least this long ends a phrase, in beats (default "1/2")
        tracks: Only these tracks (default all)
        sections: Only these sections (default all)
    """

    name = "phrasing"
    depth: int = 14
    ending: int = 8
    gap: str = "1/2"
    tracks: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        gap = Fraction(self.gap)
        for notes in _by_track(op, self.tracks, self.sections):
            phrase: list[list[event.NoteOp]] = []
            end = None
            for onset in _onsets(notes):
                if phrase and end is not None and onset[0].start.data - end >= gap:
                    self._shape(phrase)
                    phrase = []
                phrase.append(onset)
                end = max(n.start.data + n.dur.data for n in onset)
            if phrase:
                self._shape(phrase)

    def _shape(self, phrase: list[list[event.NoteOp]]) -> None:
        if len(phrase) < 2:
            return
        heights = [max(n.pitch.value.data for n in onset) for onset in phrase]
        peak = heights.index(max(heights))
        last = len(phrase) - 1
        for index, onset in enumerate(phrase):
            if index <= peak:
                rise = Fraction(index, peak) if peak else Fraction(1)
            else:
                rise = Fraction(last - index, last - peak)
            change = round(self.depth * (rise - Fraction(1, 2)))
            if index == last:
                change -= self.ending
            for note in onset:
                _set_velocity(note, note.vel.value.data + change)


@dataclass(frozen=True)
class Legato(ModulePass):
    """
    Join a line's notes: each is held until the next begins.

    Args:
        overlap: Ticks each note runs into the next (default 10). A synth with glide
            slides between overlapping notes; a repeated pitch never overlaps itself.
        max_gap: Only a note followed within this many beats is held on, so a
            real rest stays a rest (default "1/2")
        tracks: Only these tracks (default all)
        sections: Only these sections (default all)
    """

    name = "legato"
    overlap: int = 10
    max_gap: str = "1/2"
    tracks: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        reach = Fraction(self.max_gap)
        overlap = Fraction(self.overlap, PPQ)
        for notes in _by_track(op, self.tracks, self.sections):
            onsets = _onsets(notes)
            for current, following in zip(onsets, onsets[1:], strict=False):
                next_start = following[0].start.data
                next_pitches = {n.pitch.value.data for n in following}
                for note in current:
                    start = note.start.data
                    if next_start - (start + note.dur.data) > reach:
                        continue
                    extra = Fraction(0) if note.pitch.value.data in next_pitches else overlap
                    _set_time(note, start, next_start - start + extra)


_LEVELS = {
    "pp": Fraction(11, 20),
    "p": Fraction(7, 10),
    "mp": Fraction(17, 20),
    "mf": Fraction(1),
    "f": Fraction(23, 20),
    "ff": Fraction(13, 10),
}


def _mark(text: str) -> tuple[Fraction, Fraction]:
    """ "p" -> (p, p); "p<f" -> (p, f)."""
    for sign in "<>":
        if sign in text:
            start, _, end = text.partition(sign)
            levels = (_LEVELS.get(start.strip()), _LEVELS.get(end.strip()))
            if None in levels or (sign == "<") != (levels[1] > levels[0]):
                break
            return levels[0], levels[1]
    else:
        if text.strip() in _LEVELS:
            level = _LEVELS[text.strip()]
            return level, level
    raise ValueError(
        f"{text!r} is not a dynamic: use pp, p, mp, mf, f or ff, or a swell such as p<f or f>p"
    )


@dataclass(frozen=True)
class Dynamics(ModulePass):
    """
    How loud each section is played, as dynamics marks.

    Velocities are scaled against mf, which leaves them as written. A swell such as
    "p<f" moves from one level to the other across the section, so a pre-chorus
    can build into a chorus and an outro fade into silence.

    Args:
        marks: (section, mark) pairs, such as (("verse", "p"), ("pre", "p<f"))
        tracks: Only these tracks (default all, drums included)
    """

    name = "dynamics"
    marks: tuple[tuple[str, str], ...] = ()
    tracks: tuple[str, ...] = ()

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        marks = {section: _mark(text) for section, text in self.marks}
        spans = {s.tag.data: (s.at.data, s.length.data) for s in _stream(op).sections()}
        for note in _selected(op, self.tracks, tuple(marks)):
            tag = loc_key(note.location).partition("/")[0]
            begin, end = marks[tag.partition("#")[0]]
            at, length = spans.get(tag, (note.start.data, Fraction(1)))
            through = min(max((note.start.data - at) / length, Fraction(0)), Fraction(1))
            level = begin + (end - begin) * through
            _set_velocity(note, round(note.vel.value.data * level))
