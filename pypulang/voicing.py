"""
Chord voicing.

A voicing strategy says which arrangements of a chord are acceptable. It does not
choose between them: it returns every candidate that fits the register, and the
`voice-lead` pass picks the path through the progression that moves least. Keeping
those apart is what lets one strategy serve both a single chord and a whole chart.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pypulang.harmony import ChordShape, ChordTone, chord_shape
from pypulang.ir.intent import Chord, Key
from pypulang.scales import get_scale_pitches, pitch_class_to_semitone

Voicing = list[int]


@dataclass(frozen=True)
class Register:
    """The MIDI range a voicing must fit in."""

    low: int
    high: int

    @property
    def centre(self) -> float:
        return (self.low + self.high) / 2


DEFAULT_REGISTER = Register(48, 79)

Strategy = Callable[[ChordShape, Chord, Key, Register], list[Voicing]]
STRATEGIES: dict[str, Strategy] = {}


def strategy(name: str) -> Callable[[Strategy], Strategy]:
    def register(function: Strategy) -> Strategy:
        STRATEGIES[name] = function
        return function

    return register


def stack(pitch_classes: list[int], bottom: int) -> Voicing:
    """Build upward from `bottom`, each note the nearest one above the last."""
    pitches = [bottom]
    for pc in pitch_classes[1:]:
        gap = (pc - pitches[-1]) % 12 or 12
        pitches.append(pitches[-1] + gap)
    return pitches


def place(shape: list[int], register: Register) -> list[Voicing]:
    """Every octave placement of a bottom-to-top list of pitch classes that fits."""
    candidates = []
    for bottom in range(register.low, register.high + 1):
        if bottom % 12 != shape[0] % 12:
            continue
        pitches = stack(shape, bottom)
        if pitches[-1] <= register.high:
            candidates.append(pitches)
    return candidates


def _pcs(shape: ChordShape, tones: list[ChordTone]) -> list[int]:
    return [shape.pitch_class(t) for t in tones]


def _rotations(items: list[int]) -> list[list[int]]:
    return [items[i:] + items[:i] for i in range(len(items))]


def _essential(shape: ChordShape, limit: int) -> list[ChordTone]:
    """Up to `limit` tones, dropping the fifth and then the root, as players do."""
    tones = list(shape.tones)
    for name in ("5", "1"):
        if len(tones) > limit:
            tones = [t for t in tones if t.function != name]
    return tones[:limit] if len(tones) > limit else tones


@strategy("close")
def close(shape: ChordShape, chord: Chord, key: Key, register: Register) -> list[Voicing]:
    """Every inversion in close position."""
    pcs = _pcs(shape, _essential(shape, 5))
    return [v for rotation in _rotations(pcs) for v in place(rotation, register)]


@strategy("shell")
def shell(shape: ChordShape, chord: Chord, key: Key, register: Register) -> list[Voicing]:
    """Third and seventh, with one colour on top when the chord has one."""
    guide = [t for t in (shape.third, shape.seventh) if t is not None]
    if len(guide) < 2:
        return close(shape, chord, key, register)
    pcs = _pcs(shape, guide)
    colours = shape.colours()
    candidates = []
    for pair in (pcs, pcs[::-1]):
        top = [shape.pitch_class(colours[0])] if colours and colours[0].function != "5" else []
        candidates.extend(place(pair + top, register))
    return candidates


@strategy("rootless")
def rootless(shape: ChordShape, chord: Chord, key: Key, register: Register) -> list[Voicing]:
    """
    The two four-note left-hand forms, with no root: the bass has that.

    Form A runs 3-5-7-9 and form B runs 7-9-3-5, with 13 standing in for 5 on a
    dominant and an altered tension for the natural one wherever the chord has it.
    """
    third, seventh = shape.third, shape.seventh
    if third is None or seventh is None:
        return close(shape, chord, key, register)
    lower = shape.find("b13", "13", "#11", "#5", "b5", "5")
    spare = [t for t in shape.colours() if t != lower and t.function != "11"]
    upper = shape.find("#9", "b9", "9") or (spare[0] if spare else None)
    forms = []
    for first, second, third_note, fourth in (
        (third, lower, seventh, upper),
        (seventh, upper, third, lower),
    ):
        tones = [t for t in (first, second, third_note, fourth) if t is not None]
        forms.append(_pcs(shape, tones))
    return [v for form in forms for v in place(form, register)]


@strategy("drop2")
def drop2(shape: ChordShape, chord: Chord, key: Key, register: Register) -> list[Voicing]:
    """Four-note close position with the second voice from the top dropped an octave."""
    pcs = _pcs(shape, _essential(shape, 4))
    candidates = []
    wide = Register(register.low, register.high + 12)
    for rotation in _rotations(pcs):
        for closed in place(rotation, wide):
            if len(closed) < 3:
                continue
            voiced = sorted([*closed[:-2], closed[-2] - 12, closed[-1]])
            if voiced[0] >= register.low and voiced[-1] <= register.high:
                candidates.append(voiced)
    return candidates or close(shape, chord, key, register)


@strategy("quartal")
def quartal(shape: ChordShape, chord: Chord, key: Key, register: Register) -> list[Voicing]:
    """Fourths stacked within the scale, from each scale tone that belongs to the chord."""
    root = pitch_class_to_semitone(key.root)
    scale = [(root + s) % 12 for s in get_scale_pitches(key)]
    chord_pcs = set(_pcs(shape, list(shape.tones)))
    candidates = []
    for index, pc in enumerate(scale):
        if pc not in chord_pcs:
            continue
        pcs = [scale[(index + 3 * step) % 7] for step in range(4)]
        for voicing in place(pcs, register):
            candidates.append(voicing)
    return candidates or close(shape, chord, key, register)


@strategy("upper_structure")
def upper_structure(shape: ChordShape, chord: Chord, key: Key, register: Register) -> list[Voicing]:
    """
    A major triad from the tensions, over the guide tones.

    Altered dominants take the triad on the flat sixth, which is b13-root-#9. Chords
    with a sharp eleventh take it on the second, 9-#11-13. Anything else plays rootless.
    """
    third, seventh = shape.third, shape.seventh
    if third is None or seventh is None:
        return rootless(shape, chord, key, register)
    names = {t.function for t in shape.tones}
    if names & {"b13", "#9"}:
        triad_root = shape.root + 8
    elif "#11" in names:
        triad_root = shape.root + 2
    elif "b9" in names:
        triad_root = shape.root + 9
    else:
        return rootless(shape, chord, key, register)
    triad = [triad_root % 12, (triad_root + 4) % 12, (triad_root + 7) % 12]
    guide = _pcs(shape, [third, seventh])
    candidates = []
    for order in (guide, guide[::-1]):
        for rotation in _rotations(triad):
            candidates.extend(place(order + rotation, register))
    return candidates


@strategy("wide")
def wide(shape: ChordShape, chord: Chord, key: Key, register: Register) -> list[Voicing]:
    """
    Root and fifth low, the colour high, and the top note doubled an octave down.

    This is the big open stack that a detuned saw patch wants. Seconds and thirds
    down low turn to mud through unison voices, so they are kept to the upper half.
    """
    uppers = _pcs(shape, [t for t in shape.tones if t.function not in ("1", "5")])
    if not uppers:
        uppers = _pcs(shape, list(shape.tones))
    fifth = shape.find("5", "b5", "#5")
    bottom_pcs = [shape.root] + ([shape.pitch_class(fifth)] if fifth else [])
    split = int(register.low + (register.high - register.low) * 0.4)
    candidates = []
    for base in place(bottom_pcs, Register(register.low, split)):
        for rotation in _rotations(uppers):
            for top in place(rotation, Register(max(base[-1] + 3, split), register.high)):
                doubled = top[-1] - 12
                voiced = sorted({*base, *top, doubled})
                candidates.append(voiced)
    return candidates or close(shape, chord, key, register)


def candidates_for(name: str, chord: Chord, key: Key, register: Register) -> list[Voicing]:
    """
    Every voicing a strategy allows for a chord.

    Raises:
        KeyError: If no strategy has that name
    """
    if name not in STRATEGIES:
        raise KeyError(f"Unknown voicing: {name}. Available: {sorted(STRATEGIES)}")
    shape = chord_shape(chord, key)
    voicings = STRATEGIES[name](shape, chord, key, register)
    if not voicings and name != "close":
        # A narrow register can rule out a whole strategy for one chord. Playing that
        # chord in close position beats failing the compile over it.
        voicings = close(shape, chord, key, register)
    if shape.bass is not None:
        voicings = [_with_bass(v, shape.bass) for v in voicings]
    unique = {tuple(v): v for v in voicings}
    return [unique[k] for k in sorted(unique)]


def _with_bass(voicing: Voicing, bass_pc: int) -> Voicing:
    gap = (voicing[0] - bass_pc) % 12 or 12
    return [voicing[0] - gap, *voicing]


# -----------------------------------------------------------------------------
# Voice leading
# -----------------------------------------------------------------------------


def motion(previous: Voicing, current: Voicing) -> float:
    """
    How far the voices travel between two voicings.

    Voices are paired from the top, because the top is what a listener follows.
    A leap there costs extra, and a tone held between chords earns a little back.
    """
    pairs = list(zip(reversed(previous), reversed(current), strict=False))
    cost = float(sum(abs(a - b) for a, b in pairs))
    leap = abs(previous[-1] - current[-1])
    cost += 2.0 * max(0, leap - 4)
    cost += abs(len(previous) - len(current))
    cost -= 0.5 * len(set(previous) & set(current))
    return cost


def _placement(voicing: Voicing, register: Register) -> float:
    """What a voicing costs by itself: drifting from the middle, and mud down low."""
    mean = sum(voicing) / len(voicing)
    cost = 0.3 * abs(mean - register.centre)
    for low, high in zip(voicing, voicing[1:], strict=False):
        if low < 52 and high - low < 5:
            cost += 8.0
    return cost


def lead_voices(options: list[list[Voicing]], register: Register) -> list[Voicing]:
    """
    Choose one voicing per chord so the whole progression moves least.

    This is a shortest path through the candidates, solved exactly. A greedy choice
    per chord can walk the voices out of the register and be unable to come back.
    """
    if not options:
        return []
    best = [(_placement(v, register), -1) for v in options[0]]
    trail = [best]
    for previous_options, current_options in zip(options, options[1:], strict=False):
        previous_best = trail[-1]
        row = []
        for voicing in current_options:
            base = _placement(voicing, register)
            scores = [
                (previous_best[i][0] + motion(p, voicing) + base, i)
                for i, p in enumerate(previous_options)
            ]
            row.append(min(scores))
        trail.append(row)

    index = min(range(len(trail[-1])), key=lambda i: trail[-1][i][0])
    chosen = []
    for step in range(len(options) - 1, -1, -1):
        chosen.append(options[step][index])
        index = trail[step][index][1]
    chosen.reverse()
    return chosen


def total_motion(voicings: list[Voicing]) -> float:
    """The semitones all voices travel across a progression, for comparing voicings."""
    return sum(
        sum(abs(a - b) for a, b in zip(reversed(p), reversed(c), strict=False))
        for p, c in zip(voicings, voicings[1:], strict=False)
    )
