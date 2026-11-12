"""
Melody as motifs: a short idea, stated and then developed.

A melody that is a list of notes has nothing to come back to, and no way to say
"the same idea, a step higher" except by rewriting every note. Here a melody is a
phrase of motifs, and a motif is written once in scale degrees:

    song.motif("hook", "5/8 6 1'/4 7/8 5/4. 3/8")
    verse.track("lead").melody("hook; hook +1; hook inv end 1; rest 2")

Motif tokens are a scale degree 1-7, optionally flattened or sharpened ("b7",
"#4") and moved by octaves ("1'" up, "5," down), then a note value as in `line`:
1, 2, 4, 8, 16, with "." for dotted and "t" for a triplet, carried over until the
next one is given. "r" is a rest. Suffixes: ">" accents a note, "?" makes it a
ghost, "!" plays it staccato, "~" ties it into the next.

A phrase is placements separated by ";", played one after another. A placement is
a motif's name and any of these, applied left to right:

    +n / -n     move every note n scale steps (a sequence)
    ^ / v       an octave up or down
    inv         invert: mirror its intervals around the first note
    rev         play it backwards
    x2, x1/2    stretch or squeeze its rhythm
    first n     only its first n notes; last n, its last n
    end d       end on degree d: the question and answer of a phrase
    vary s      ornament it: passing and neighbour notes, the same for the same s
    early v     start a note value early (an anticipation); late v, later

"rest v" is a placement of silence. Degrees are resolved in the section's key, and
each placement is put in the octave nearest to where the line already is, keeping to
the track's range: a sequence that climbs a step past the top stays put rather than
dropping an octave, and one that climbs further does drop. With `fit`, a note held
on a strong beat that clashes with the chord under it, a semitone above one of its
tones, moves to the nearest note that belongs; tensions such as 9ths and 13ths are
left alone.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, replace
from fractions import Fraction

from pypulang.ir.intent import Chord, Key
from pypulang.lines import _value
from pypulang.resolution import resolve_chord
from pypulang.scales import get_scale_pitches, pitch_class_to_semitone

_TOKEN_RE = re.compile(
    r"^(?:(?P<rest>r)|(?P<acc>[#b])?(?P<degree>[1-7])(?P<octave>[',]*))"
    r"(?:/(?P<value>\d+)(?P<dot>\.)?(?P<triplet>t)?)?"
    r"(?P<suffix>[>?!~]*)$"
)


@dataclass(frozen=True)
class MotifNote:
    """A note in scale steps from degree 1 of the key's middle octave, in beats."""

    step: int  # 0 is degree 1, 7 is degree 1 an octave up
    accidental: int
    start: Fraction
    dur: Fraction
    velocity_scale: Fraction = Fraction(1)
    articulation: str | None = None


@dataclass(frozen=True)
class Motif:
    notes: tuple[MotifNote, ...]
    length: Fraction  # including trailing rests

    def shifted(self, beats: Fraction) -> Motif:
        return Motif(tuple(replace(n, start=n.start + beats) for n in self.notes), self.length)


@dataclass(frozen=True)
class MelodyNote:
    """A realized note: MIDI pitch, beats from the phrase start, velocity scale."""

    pitch: int
    start: Fraction
    dur: Fraction
    velocity_scale: Fraction
    articulation: str | None = None


def parse_motif(text: str) -> Motif:
    """
    Read a motif written in scale degrees.

    Raises:
        ValueError: On a token that cannot be read
    """
    notes: list[MotifNote] = []
    at = Fraction(0)
    value = Fraction(1)
    tied = False
    for token in text.replace("|", " ").split():
        m = _TOKEN_RE.match(token)
        if m is None:
            raise ValueError(f"Cannot read {token!r} in motif {text!r}")
        if m.group("value"):
            value = _value(m.group("value"), bool(m.group("dot")), bool(m.group("triplet")))
        if m.group("rest"):
            at += value
            tied = False
            continue
        octave = m.group("octave").count("'") - m.group("octave").count(",")
        step = int(m.group("degree")) - 1 + 7 * octave
        accidental = {"#": 1, "b": -1, None: 0}[m.group("acc")]
        suffix = m.group("suffix")
        if tied and notes and (notes[-1].step, notes[-1].accidental) == (step, accidental):
            notes[-1] = replace(notes[-1], dur=notes[-1].dur + value)
        else:
            scale = (
                Fraction(6, 5)
                if ">" in suffix
                else Fraction(1, 2)
                if "?" in suffix
                else Fraction(1)
            )
            articulation = "staccato" if "!" in suffix else None
            notes.append(MotifNote(step, accidental, at, value, scale, articulation))
        tied = "~" in suffix
        at += value
    if not notes:
        raise ValueError(f"Motif {text!r} has no notes")
    return Motif(tuple(notes), at)


# -- development ------------------------------------------------------------------


def _respaced(notes: list[MotifNote]) -> Motif:
    """Notes moved so the first starts at 0; the length runs to the last one's end."""
    if not notes:
        return Motif((), Fraction(0))
    first = notes[0].start
    moved = tuple(replace(n, start=n.start - first) for n in notes)
    return Motif(moved, max(n.start + n.dur for n in moved))


def develop(motif: Motif, op: str, arg: str | None, seed_text: str = "") -> Motif:
    """Apply one development to a motif."""
    notes = list(motif.notes)
    if op in ("+", "-"):
        n = int(arg) * (1 if op == "+" else -1)
        return Motif(tuple(replace(x, step=x.step + n) for x in notes), motif.length)
    if op in ("^", "v"):
        n = 7 if op == "^" else -7
        return Motif(tuple(replace(x, step=x.step + n) for x in notes), motif.length)
    if op == "inv":
        pivot = notes[0].step
        return Motif(
            tuple(replace(x, step=2 * pivot - x.step, accidental=-x.accidental) for x in notes),
            motif.length,
        )
    if op == "rev":
        flipped = [replace(x, start=motif.length - x.start - x.dur) for x in reversed(notes)]
        return Motif(tuple(flipped), motif.length)
    if op == "x":
        r = Fraction(arg)
        return Motif(
            tuple(replace(x, start=x.start * r, dur=x.dur * r) for x in notes), motif.length * r
        )
    if op == "first":
        kept = notes[: int(arg)]
        return Motif(tuple(kept), max(n.start + n.dur for n in kept))
    if op == "last":
        return _respaced(notes[-int(arg) :])
    if op == "end":
        target = int(arg) - 1
        last = notes[-1]
        # The octave of `target` nearest to where the line already is.
        candidates = [target + 7 * k for k in range(-3, 4)]
        step = min(candidates, key=lambda s: abs(s - last.step))
        notes[-1] = replace(last, step=step, accidental=0)
        return Motif(tuple(notes), motif.length)
    if op == "vary":
        return _ornament(motif, f"{seed_text}|{arg}")
    if op in ("early", "late"):
        beats = _value(*_value_parts(arg))
        return motif.shifted(-beats if op == "early" else beats)
    raise ValueError(f"No development called {op!r}")


def _value_parts(text: str) -> tuple[str, bool, bool]:
    m = re.fullmatch(r"(\d+)(\.)?(t)?", text)
    if m is None:
        raise ValueError(f"{text!r} is not a note value such as 8, 4. or 8t")
    return m.group(1), bool(m.group(2)), bool(m.group(3))


def _ornament(motif: Motif, seed: str) -> Motif:
    """
    Split some longer notes into a note and a passing or neighbour note.

    The same seed gives the same ornaments, so a varied motif stays put across
    recompiles, as humanized timing does.
    """
    rng = random.Random(seed)
    notes = list(motif.notes)
    result: list[MotifNote] = []
    for index, note in enumerate(notes):
        following = notes[index + 1] if index + 1 < len(notes) else None
        if note.dur >= Fraction(1) and rng.random() < 0.6:
            half = note.dur / 2
            if following is not None and abs(following.step - note.step) >= 2:
                # A passing note, a step toward where the line goes next.
                towards = 1 if following.step > note.step else -1
            else:
                towards = rng.choice((-1, 1))  # a neighbour, above or below
            result.append(replace(note, dur=half))
            result.append(
                replace(
                    note,
                    step=note.step + towards,
                    accidental=0,
                    start=note.start + half,
                    dur=half,
                    velocity_scale=note.velocity_scale * Fraction(4, 5),
                )
            )
        else:
            result.append(note)
    return Motif(tuple(result), motif.length)


@dataclass(frozen=True)
class Placement:
    """One entry of a phrase: a developed motif, or a rest."""

    motif: str | None  # None for a rest
    ops: tuple[tuple[str, str | None], ...]
    rest: Fraction = Fraction(0)


_OP_RE = re.compile(
    r"^(?:(?P<sign>[+-])(?P<n>\d+)|(?P<oct>[\^v])|x(?P<ratio>\d+(?:/\d+)?)|(?P<word>[a-z]+))$"
)


def parse_phrase(text: str) -> list[Placement]:
    """
    Read a phrase: placements separated by ";".

    Raises:
        ValueError: On a development that cannot be read
    """
    placements = []
    for part in [p.strip() for p in text.split(";") if p.strip()]:
        words = part.split()
        if words[0] == "rest":
            if len(words) != 2:
                raise ValueError(f"'rest' takes one note value, as in 'rest 2': {part!r}")
            placements.append(Placement(None, (), _value(*_value_parts(words[1]))))
            continue
        name, rest = words[0], words[1:]
        ops: list[tuple[str, str | None]] = []
        index = 0
        while index < len(rest):
            m = _OP_RE.match(rest[index])
            if m is None:
                raise ValueError(f"Cannot read {rest[index]!r} in {part!r}")
            if m.group("sign"):
                ops.append((m.group("sign"), m.group("n")))
            elif m.group("oct"):
                ops.append((m.group("oct"), None))
            elif m.group("ratio"):
                ops.append(("x", m.group("ratio")))
            else:
                word = m.group("word")
                if word in ("inv", "rev"):
                    ops.append((word, None))
                elif word in ("first", "last", "end", "vary", "early", "late"):
                    if index + 1 >= len(rest):
                        raise ValueError(f"'{word}' needs a value in {part!r}")
                    ops.append((word, rest[index + 1]))
                    index += 1
                else:
                    raise ValueError(f"No development called {word!r} in {part!r}")
            index += 1
        placements.append(Placement(name, tuple(ops)))
    return placements


# -- realizing --------------------------------------------------------------------


_TONIC = MotifNote(0, 0, Fraction(0), Fraction(1))


def _pitch(note: MotifNote, key: Key, octave: int) -> int:
    scale = get_scale_pitches(key)
    root = pitch_class_to_semitone(key.root)
    degree, octaves = note.step % 7, note.step // 7
    return 12 * (octave + 1) + root + scale[degree] + note.accidental + 12 * octaves


def _chord_at(
    spans: list[tuple[Chord, Fraction, Fraction]], at: Fraction
) -> tuple[Chord, Fraction] | None:
    for chord, start, beats in spans:
        if start <= at < start + beats:
            return chord, start
    return None


def _fits(pitch: int, tones: set[int]) -> bool:
    """A chord tone, or a tension that is not a semitone above one."""
    pc = pitch % 12
    return pc in tones or (pc - 1) % 12 not in tones


def _fit(pitch: int, tones: set[int], scale_pcs: set[int]) -> int:
    """The nearest pitch that fits, preferring ones in the key, then chord tones."""
    if _fits(pitch, tones):
        return pitch
    for distance in (1, 2, 3):
        for candidate in (pitch - distance, pitch + distance):
            if candidate % 12 in tones:
                return candidate
    for distance in (1, 2):
        for candidate in (pitch - distance, pitch + distance):
            if candidate % 12 in scale_pcs and _fits(candidate, tones):
                return candidate
    return pitch


def _place(motif: Motif, key: Key, anchor: int, low: int, high: int) -> list[int]:
    """
    The motif's pitches in the octave that joins the line best.

    A leap into the motif costs its size in semitones and each semitone outside the
    range costs four, so a sequence climbing a step past the top stays where it is
    rather than dropping an octave, and one climbing a fourth past it does drop.
    """

    def cost(octave: int) -> int:
        pitches = [_pitch(n, key, octave) for n in motif.notes]
        outside = sum(max(0, low - p) + max(0, p - high) for p in (min(pitches), max(pitches)))
        return abs(pitches[0] - anchor) + 4 * outside

    octave = min(range(0, 9), key=cost)
    return [_pitch(n, key, octave) for n in motif.notes]


def realize(
    phrase: str,
    motifs: dict[str, str],
    key: Key,
    spans: list[tuple[Chord, Fraction, Fraction]],
    bar_beats: Fraction,
    low: int = 60,
    high: int = 84,
    fit: bool = True,
    seed: str = "",
) -> list[MelodyNote]:
    """
    Turn a phrase into notes, in beats from the start of its section.

    Args:
        phrase: The phrase text
        motifs: Motif names to their text
        key: The section's key
        spans: (chord, start beat, length) under the phrase, as the section plays it
        bar_beats: Beats in a bar, which decides the strong beats
        low, high: The MIDI range the line keeps to
        fit: Move clashing notes on strong beats onto the chord
        seed: Makes `vary` differ between places that use the same motif

    Raises:
        ValueError: On a motif that is not defined, or text that cannot be read
    """
    parsed = {name: parse_motif(text) for name, text in motifs.items()}
    scale_pcs = {(pitch_class_to_semitone(key.root) + s) % 12 for s in get_scale_pitches(key)}
    centre = (low + high) // 2
    previous: int | None = None
    at = Fraction(0)
    result: list[MelodyNote] = []
    for index, placement in enumerate(parse_phrase(phrase)):
        if placement.motif is None:
            at += placement.rest
            continue
        if placement.motif not in parsed:
            raise ValueError(f"No motif called {placement.motif!r}; define it with song.motif()")
        motif = parsed[placement.motif]
        for op, arg in placement.ops:
            motif = develop(motif, op, arg, seed_text=f"{seed}/{index}")
        if previous is None:
            # The first placement sits in the octave whose tonic is nearest the middle
            # of the range, so "1" is that tonic and "5," the fifth below it, and a
            # transposed melody moves with the key instead of jumping an octave.
            home = min(range(0, 9), key=lambda o: abs(_pitch(_TONIC, key, o) - centre))
            anchor = _pitch(motif.notes[0], key, home)
        else:
            anchor = previous
        pitches = _place(motif, key, anchor, low, high)
        for note, pitch in zip(motif.notes, pitches, strict=True):
            start = at + note.start
            if fit:
                sounding = _chord_at(spans, start)
                if sounding is not None:
                    chord, chord_start = sounding
                    strong = start == chord_start or (
                        start % 1 == 0 and start % (bar_beats / 2) == 0
                    )
                    if strong or note.dur >= 1:
                        tones = {p % 12 for p in resolve_chord(chord, key)}
                        pitch = _fit(pitch, tones, scale_pcs)
            if start >= 0:
                result.append(
                    MelodyNote(pitch, start, note.dur, note.velocity_scale, note.articulation)
                )
            previous = pitch
        at += motif.length
    return result
