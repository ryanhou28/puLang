"""
Chord vocabulary for puLang.

This module owns what a chord *is*: which intervals its tokens stand for, how a
chord is written as text, and how jazz chart symbols ("G13b9", "Fmaj9#11/A") map
onto the roman-numeral `Chord` the IR carries.

An unknown token is an error. The previous resolver skipped tokens it did not
recognise, so `V7(b9)` silently played as a plain `V7`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pypulang.ir.intent import Chord, Key
from pypulang.scales import get_scale_pitches, pitch_class_to_semitone

# Every token `Chord.extensions` may hold.
KNOWN_TOKENS = frozenset(
    {
        "6",
        "7",
        "maj7",
        "min7",
        "dim7",
        "9",
        "11",
        "13",
        "69",
        "add2",
        "add4",
        "add9",
        "add11",
        "add13",
        "sus2",
        "sus4",
        "b5",
        "#5",
        "b9",
        "#9",
        "#11",
        "b13",
        "alt",
        "no1",
        "no3",
        "no5",
    }
)

_SEVENTHS = ("6", "69", "7", "maj7", "min7", "dim7")


@dataclass(frozen=True)
class ChordTone:
    """One note of a chord: semitones above the root, and what it is called."""

    interval: int
    function: str


def _triad(quality: str) -> tuple[int, int]:
    if quality == "major":
        return 4, 7
    if quality == "minor":
        return 3, 7
    if quality == "diminished":
        return 3, 6
    if quality == "augmented":
        return 4, 8
    raise ValueError(f"Unknown chord quality: {quality}")


def chord_intervals(quality: str, extensions: tuple[str, ...] = ()) -> list[ChordTone]:
    """
    The intervals of a chord, lowest first, one entry per distinct interval.

    Args:
        quality: "major", "minor", "diminished", "augmented"
        extensions: Tokens from `KNOWN_TOKENS`, in any order

    Raises:
        ValueError: If a token is not in `KNOWN_TOKENS`
    """
    for token in extensions:
        if token not in KNOWN_TOKENS:
            raise ValueError(f"Unknown chord token {token!r}. Known tokens: {sorted(KNOWN_TOKENS)}")

    third, fifth = _triad(quality)
    tones: dict[int, str] = {0: "1", third: "3", fifth: "5"}
    has_seventh = any(t in extensions for t in _SEVENTHS)

    def implied_seventh() -> None:
        if not has_seventh and "alt" not in extensions:
            tones[10] = "7"

    for token in extensions:
        if token == "6":
            tones[9] = "6"
        elif token == "69":
            tones[9] = "6"
            tones[14] = "9"
        elif token in ("7", "min7"):
            tones[10] = "7"
        elif token == "maj7":
            tones[11] = "7"
        elif token == "dim7":
            tones[9] = "7"
        elif token == "9":
            implied_seventh()
            tones[14] = "9"
        elif token == "11":
            implied_seventh()
            tones[14] = "9"
            tones[17] = "11"
        elif token == "13":
            # The natural 11 is left out: over a major third it is the avoid note
            # every player drops, and "13" on a chart never means it.
            implied_seventh()
            tones[14] = "9"
            tones[21] = "13"
        elif token in ("add2", "add9"):
            tones[2 if token == "add2" else 14] = "9"
        elif token in ("add4", "add11"):
            tones[5 if token == "add4" else 17] = "11"
        elif token == "add13":
            tones[21] = "13"
        elif token == "b9":
            tones[13] = "b9"
        elif token == "#9":
            tones[15] = "#9"
        elif token == "#11":
            tones[18] = "#11"
        elif token == "b13":
            tones[20] = "b13"
        elif token == "alt":
            tones[10] = "7"
            tones[13] = "b9"
            tones[15] = "#9"
            tones[20] = "b13"
            tones.pop(fifth, None)

    # An altered tension replaces the natural one that a higher extension implied.
    if ("b9" in extensions or "#9" in extensions) and "9" not in extensions:
        tones.pop(14, None)
    if "#11" in extensions and "11" not in extensions:
        tones.pop(17, None)

    # Removals run last so their position among the tokens cannot matter.
    if "sus2" in extensions or "sus4" in extensions:
        tones.pop(third, None)
        if "sus2" in extensions:
            tones[2] = "2"
        if "sus4" in extensions:
            tones[5] = "4"
    if "b5" in extensions:
        tones.pop(fifth, None)
        tones[6] = "b5"
    if "#5" in extensions:
        tones.pop(fifth, None)
        tones[8] = "#5"
    if "no1" in extensions:
        tones.pop(0, None)
    if "no3" in extensions:
        tones.pop(third, None)
    if "no5" in extensions:
        tones.pop(fifth, None)

    return [ChordTone(i, tones[i]) for i in sorted(tones)]


# -----------------------------------------------------------------------------
# Roman numerals as text
# -----------------------------------------------------------------------------

_ROMAN_RE = re.compile(
    r"""^(?P<acc>[b#]?)
        (?P<num>VII|VI|IV|V|III|II|I|vii|vi|iv|v|iii|ii|i)
        (?P<qual>[°+mM]?)
        (?:\((?P<ext>[^)]*)\))?
        (?:\^(?P<inv>\d))?
        (?:/(?P<sec>[IViv]+))?
        (?:\|(?P<bass>\d+))?$""",
    re.VERBOSE,
)


def format_roman(chord: Chord) -> str:
    """
    Write a chord as text that `parse_roman` reads back exactly.

    Examples: "V(7,b9)", "bVII(maj7)", "ii(7)^1", "V/V", "IV|7"
    """
    parts = []
    if chord.altered_root:
        parts.append("b" if chord.altered_root < 0 else "#")
    parts.append(chord.numeral)
    default = "major" if chord.is_uppercase else "minor"
    if chord.quality == "diminished":
        parts.append("°")
    elif chord.quality == "augmented":
        parts.append("+")
    elif chord.quality != default:
        parts.append("m" if chord.quality == "minor" else "M")
    if chord.extensions:
        parts.append("(" + ",".join(chord.extensions) + ")")
    if chord.inversion:
        parts.append(f"^{chord.inversion}")
    if chord.secondary:
        parts.append(f"/{chord.secondary}")
    if chord.bass_offset is not None:
        parts.append(f"|{chord.bass_offset}")
    return "".join(parts)


def parse_roman(text: str) -> Chord:
    """Read a chord written by `format_roman`."""
    m = _ROMAN_RE.match(text.strip())
    if m is None:
        raise ValueError(f"Cannot parse roman numeral: {text!r}")
    numeral = m.group("num")
    quality = "major" if numeral.isupper() else "minor"
    qual = m.group("qual")
    if qual == "°":
        quality = "diminished"
    elif qual == "+":
        quality = "augmented"
    elif qual == "m":
        quality = "minor"
    elif qual == "M":
        quality = "major"
    ext = m.group("ext")
    extensions = tuple(t.strip() for t in ext.split(",") if t.strip()) if ext else ()
    bass = m.group("bass")
    return Chord(
        numeral=numeral,
        quality=quality,
        extensions=extensions,
        inversion=int(m.group("inv") or 0),
        altered_root={"": 0, "b": -1, "#": 1}[m.group("acc")],
        secondary=m.group("sec"),
        bass_offset=int(bass) if bass is not None else None,
    )


# -----------------------------------------------------------------------------
# Chart symbols
# -----------------------------------------------------------------------------

_SYMBOL_ROOT_RE = re.compile(r"^([A-G](?:#|b)?)(.*)$")

# Longest spellings first, so "maj7" is never read as "m" + "aj7".
_SYMBOL_TOKENS: list[tuple[str, tuple[str | None, tuple[str, ...]]]] = [
    ("minmaj7", ("minor", ("maj7",))),
    ("mMaj7", ("minor", ("maj7",))),
    ("mmaj7", ("minor", ("maj7",))),
    ("mM7", ("minor", ("maj7",))),
    ("maj13", (None, ("maj7", "13"))),
    ("maj11", (None, ("maj7", "11"))),
    ("maj9", (None, ("maj7", "9"))),
    ("maj7", (None, ("maj7",))),
    ("Maj7", (None, ("maj7",))),
    ("ma7", (None, ("maj7",))),
    ("M13", (None, ("maj7", "13"))),
    ("M9", (None, ("maj7", "9"))),
    ("M7", (None, ("maj7",))),
    ("Δ9", (None, ("maj7", "9"))),
    ("Δ7", (None, ("maj7",))),
    ("Δ", (None, ("maj7",))),
    ("maj", ("major", ())),
    ("min", ("minor", ())),
    ("dim7", ("diminished", ("dim7",))),
    ("°7", ("diminished", ("dim7",))),
    ("o7", ("diminished", ("dim7",))),
    ("dim", ("diminished", ())),
    ("°", ("diminished", ())),
    ("ø7", ("diminished", ("7",))),
    ("ø", ("diminished", ("7",))),
    ("aug", ("augmented", ())),
    ("+", ("augmented", ())),
    ("add13", (None, ("add13",))),
    ("add11", (None, ("add11",))),
    ("add9", (None, ("add9",))),
    ("add4", (None, ("add4",))),
    ("add2", (None, ("add2",))),
    ("sus2", (None, ("sus2",))),
    ("sus4", (None, ("sus4",))),
    ("sus", (None, ("sus4",))),
    ("alt", (None, ("alt",))),
    ("no5", (None, ("no5",))),
    ("no3", (None, ("no3",))),
    ("no1", (None, ("no1",))),
    ("6/9", (None, ("69",))),
    ("69", (None, ("69",))),
    ("13", (None, ("13",))),
    ("11", (None, ("11",))),
    ("b13", (None, ("b13",))),
    ("#11", (None, ("#11",))),
    ("#9", (None, ("#9",))),
    ("b9", (None, ("b9",))),
    ("#5", (None, ("#5",))),
    ("b5", (None, ("b5",))),
    ("9", (None, ("9",))),
    ("7", (None, ("7",))),
    ("6", (None, ("6",))),
    ("m", ("minor", ())),
    ("-", ("minor", ())),
]
_SYMBOL_TOKENS.sort(key=lambda entry: len(entry[0]), reverse=True)


def _degree_of(offset: int, key: Key) -> tuple[int, int]:
    """The scale degree and alteration that name `offset` semitones above the key root."""
    scale = get_scale_pitches(key)
    if offset in scale:
        return scale.index(offset) + 1, 0
    # The tritone above the tonic is #IV by convention; everything else reads as a flat.
    if offset == 6 and (5 in scale):
        return scale.index(5) + 1, 1
    for degree, pitch in enumerate(scale, start=1):
        if (pitch - 1) % 12 == offset:
            return degree, -1
    for degree, pitch in enumerate(scale, start=1):
        if (pitch + 1) % 12 == offset:
            return degree, 1
    raise ValueError(f"No scale degree near {offset} in {key}")


_NUMERALS = ("I", "II", "III", "IV", "V", "VI", "VII")


def parse_chord_symbol(symbol: str, key: Key) -> Chord:
    """
    Read a chart symbol as a roman-numeral chord in `key`.

    Examples:
        >>> parse_chord_symbol("G13b9", Key("C", "major"))
        Chord(numeral='V', ...)
        >>> parse_chord_symbol("Fmaj9#11/A", Key("C", "major")).bass_offset
        9

    Raises:
        ValueError: If any part of the symbol cannot be read
    """
    text = symbol.strip()
    bass_pc: int | None = None
    if "/" in text and not text.endswith("6/9"):
        head, _, tail = text.rpartition("/")
        if re.fullmatch(r"[A-G](#|b)?", tail):
            text = head
            bass_pc = pitch_class_to_semitone(tail)

    m = _SYMBOL_ROOT_RE.match(text)
    if m is None:
        raise ValueError(f"Cannot parse chord symbol: {symbol!r}")
    root_pc = pitch_class_to_semitone(m.group(1))
    rest = m.group(2).replace("(", "").replace(")", "").replace(",", "").replace(" ", "")

    quality: str | None = None
    extensions: list[str] = []
    while rest:
        for spelling, (token_quality, tokens) in _SYMBOL_TOKENS:
            if rest.startswith(spelling):
                if token_quality is not None:
                    quality = token_quality
                extensions.extend(t for t in tokens if t not in extensions)
                rest = rest[len(spelling) :]
                break
        else:
            raise ValueError(f"Cannot parse chord symbol {symbol!r}: stuck at {rest!r}")

    quality = quality or "major"
    key_root = pitch_class_to_semitone(key.root)
    degree, altered = _degree_of((root_pc - key_root) % 12, key)
    numeral = _NUMERALS[degree - 1]
    if quality in ("minor", "diminished"):
        numeral = numeral.lower()
    return Chord(
        numeral=numeral,
        quality=quality,
        extensions=tuple(extensions),
        altered_root=altered,
        bass_offset=None if bass_pc is None else (bass_pc - key_root) % 12,
    )


def parse_chart(chart: str, key: Key) -> list[tuple[Chord, tuple[int, int]]]:
    """
    Read a chord chart, one bar between each pair of "|".

    Chords in a bar share it equally. "%" repeats the previous bar.

    Args:
        chart: For example "Dm9 G13 | Cmaj9 | % | A7alt"
        key: The key the numerals are relative to

    Returns:
        (chord, (numerator, denominator)) pairs; the fraction is bars
    """
    result: list[tuple[Chord, tuple[int, int]]] = []
    previous: list[Chord] = []
    for bar in chart.strip().strip("|").split("|"):
        symbols = bar.split()
        if not symbols:
            raise ValueError(f"Empty bar in chart: {chart!r}")
        if symbols == ["%"]:
            if not previous:
                raise ValueError(f"'%' with no previous bar in chart: {chart!r}")
            chords = previous
        else:
            chords = [parse_chord_symbol(s, key) for s in symbols]
        for chord in chords:
            result.append((chord, (1, len(chords))))
        previous = chords
    return result


def root_pitch_class(chord: Chord, key: Key) -> int:
    """The pitch class (0-11) of a chord's root."""
    scale = get_scale_pitches(key)
    offset = scale[chord.degree - 1] + chord.altered_root
    if chord.secondary:
        target = Chord(numeral=chord.secondary)
        offset = scale[target.degree - 1] + 7
    return (pitch_class_to_semitone(key.root) + offset) % 12


def chord_symbol(chord: Chord, key: Key) -> str:
    """A compact chart-style name for a chord, for reading IR and reports."""
    sharps = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    flats = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
    names = flats if prefers_flats(key) or chord.altered_root < 0 else sharps
    quality = {"major": "", "minor": "m", "diminished": "dim", "augmented": "+"}[chord.quality]
    tokens = [t for t in chord.extensions if not (t == "dim7" and chord.quality == "diminished")]
    if chord.quality == "diminished" and "dim7" in chord.extensions:
        quality = "dim7"
    text = names[root_pitch_class(chord, key)] + quality + " ".join(tokens).replace(" ", "")
    if chord.bass_offset is not None:
        text += "/" + names[(pitch_class_to_semitone(key.root) + chord.bass_offset) % 12]
    return text


# Key signatures with flats, by the pitch class of their major-scale tonic.
_FLAT_MAJOR_TONICS = frozenset({5, 10, 3, 8, 1, 6})
_MODE_TO_MAJOR_OFFSET = {
    "major": 0,
    "minor": 3,
    "aeolian": 3,
    "dorian": 10,
    "phrygian": 8,
    "lydian": 7,
    "mixolydian": 5,
    "locrian": 1,
    "harmonic_minor": 3,
    "melodic_minor": 3,
}


def prefers_flats(key: Key) -> bool:
    """True if `key`'s signature is written with flats."""
    if "b" in key.root:
        return True
    if "#" in key.root:
        return False
    tonic = pitch_class_to_semitone(key.root)
    return (tonic + _MODE_TO_MAJOR_OFFSET[key.mode]) % 12 in _FLAT_MAJOR_TONICS
