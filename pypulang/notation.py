"""
Notation: one part of one section drawn on a staff.

The notes come in as plain numbers, MIDI pitches and beats from the section's
start, so this knows nothing about the IR. They are written as MEI, the music
encoding Verovio reads, and Verovio engraves them as SVG.

What the writing decides, because MEI states it and Verovio does not infer it:

- Spelling, in the key: a degree keeps its letter, so D minor's raised seventh is
  C#, never Db.
- Accidentals, shown where a note differs from the key signature or from an
  earlier note on the same line in the bar.
- Note values: a length is split into values that start where such a value may
  start, and tied across those splits and across barlines.
- Beams, a beat at a time (a dotted quarter in compound meters).

Each note's SVG element has the id it came in with, so a page can find the note
a click landed on, and colour, so a page can show what an edit changes. Lengths
that are not on a sixteenth grid, such as triplets, are drawn rounded to it and
reported.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from pypulang.ir.intent import Key, TimeSignature
from pypulang.motifs import degree_of
from pypulang.scales import pitch_class_to_semitone

_LETTERS = "CDEFGAB"
_NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_GRID = Fraction(1, 4)  # a sixteenth, in quarter-note beats

# Note values in quarter-note beats, longest first, and how MEI writes each.
_VALUES: list[tuple[Fraction, str, int]] = [
    (Fraction(4), "1", 0),
    (Fraction(3), "2", 1),
    (Fraction(2), "2", 0),
    (Fraction(3, 2), "4", 1),
    (Fraction(1), "4", 0),
    (Fraction(3, 4), "8", 1),
    (Fraction(1, 2), "8", 0),
    (Fraction(3, 8), "16", 1),
    (Fraction(1, 4), "16", 0),
]

# How far each mode's tonic sits above its relative major's, in semitones.
_MODE_OFFSET = {
    "major": 0,
    "ionian": 0,
    "dorian": 2,
    "phrygian": 4,
    "lydian": 5,
    "mixolydian": 7,
    "minor": 9,
    "aeolian": 9,
    "harmonic_minor": 9,
    "melodic_minor": 9,
    "locrian": 11,
}
# Fifths of each major key's tonic, by pitch class; 6 is spelt by the tonic.
_FIFTHS = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: -5, 8: -4, 3: -3, 10: -2, 5: -1}


@dataclass
class StaffNote:
    pitch: int  # MIDI
    start: Fraction  # beats from the section's start
    dur: Fraction
    id: str = ""
    color: str | None = None
    voice: int = 0


@dataclass
class Staff:
    """What one staff shows: the notes, the bars they sit in, and the chords over them."""

    notes: list[StaffNote]
    bars: int
    key: Key
    meter: TimeSignature
    first_bar: int = 1  # the number the first bar is given
    chords: list[tuple[Fraction, str]] = field(default_factory=list)  # (beat, symbol)
    bars_per_line: int = 4
    clef: str | None = None  # "G2" or "F4"; chosen from the notes when None


@dataclass
class Engraved:
    svg: str
    rounded: int = 0  # notes moved onto the sixteenth grid
    ids: dict[str, str] = field(default_factory=dict)  # element id -> the note's own id


def fifths(key: Key) -> int:
    """Sharps (positive) or flats (negative) in a key's signature."""
    tonic = pitch_class_to_semitone(key.root)
    major = (tonic - _MODE_OFFSET.get(key.mode, 0)) % 12
    count = _FIFTHS[major]
    if major == 6 and "b" in key.root:
        count = -6
    return count


def spell(pitch: int, key: Key) -> tuple[str, int, int]:
    """(letter, alteration, octave) of a pitch, spelt as a degree of the key."""
    step, accidental = degree_of(pitch, key)
    tonic_letter = _LETTERS.index(key.root[0].upper())
    letter = _LETTERS[(tonic_letter + step % 7) % 7]
    within = pitch % 12
    alter = (within - _NATURAL[letter] + 6) % 12 - 6
    if abs(alter) > 2:  # a spelling the degree cannot give; fall back to the nearest letter
        letter, alter = _nearest(within, accidental)
    octave = (pitch - alter) // 12 - 1
    return letter, alter, octave


def _nearest(within: int, prefer: int) -> tuple[str, int]:
    for letter, natural in _NATURAL.items():
        if natural == within:
            return letter, 0
    for letter, natural in _NATURAL.items():
        if (natural + (1 if prefer >= 0 else -1)) % 12 == within:
            return letter, 1 if prefer >= 0 else -1
    raise ValueError(within)


def _signature(key: Key) -> dict[str, int]:
    """Each letter's alteration under the key signature."""
    count = fifths(key)
    sharps, flats = "FCGDAEB", "BEADGCF"
    if count >= 0:
        return {letter: 1 if letter in sharps[:count] else 0 for letter in _LETTERS}
    return {letter: -1 if letter in flats[:-count] else 0 for letter in _LETTERS}


def _key_sig(key: Key) -> str:
    count = fifths(key)
    return "0" if count == 0 else f"{abs(count)}{'s' if count > 0 else 'f'}"


def _xml_id(text: str) -> str:
    return "n" + re.sub(r"[^A-Za-z0-9_-]", "_", text)


def _snap(value: Fraction) -> Fraction:
    return Fraction(round(value / _GRID)) * _GRID


def _beat_group(meter: TimeSignature) -> Fraction:
    """The span one beam covers: a beat, or a dotted quarter in 6/8, 9/8, 12/8."""
    if meter.denominator == 8 and meter.numerator % 3 == 0:
        return Fraction(3, 2)
    return Fraction(1)


def _pieces(
    at: Fraction, length: Fraction, bar: Fraction, rest: bool = False
) -> list[tuple[Fraction, str, int]]:
    """
    A length starting `at` beats into a bar, as note values, the way a part is
    written: from a beat, the longest value that fits (a whole note only from the
    bar's start); from inside a beat, values that stay inside it, except a
    syncopated quarter on an off-beat eighth that stays inside its half of the bar.
    Rests are not dotted, and a half rest starts on a half bar.
    """
    out = []
    half = bar / 2 if bar % 2 == 0 else None
    while length > 0:
        on_beat = at % 1 == 0
        for value, dur, dots in _VALUES:
            if value > length or (dots and rest) or (value >= 4 and at != 0):
                continue
            if on_beat:
                if rest and value >= 2 and half is not None and at % half != 0:
                    continue
            else:
                syncopated = (
                    not rest
                    and value == 1
                    and at % Fraction(1, 2) == 0
                    and half is not None
                    and (at + value <= half or at >= half)
                )
                within = at + value <= at // 1 + 1 and at % (value * 2 / 3 if dots else value) == 0
                if not (syncopated or within):
                    continue
            out.append((value, dur, dots))
            at += value
            length -= value
            break
        else:  # nothing fits the grid: take the smallest value
            value, dur, dots = _VALUES[-1]
            out.append((value, dur, dots))
            at += value
            length -= value
    return out


@dataclass
class _Event:
    start: Fraction
    dur: Fraction
    notes: list[StaffNote]  # empty for a rest


def _layer_events(notes: Sequence[StaffNote], total: Fraction) -> list[_Event]:
    """One voice's notes as a line of chords and rests filling the whole span."""
    by_start: dict[Fraction, list[StaffNote]] = {}
    for note in notes:
        by_start.setdefault(note.start, []).append(note)
    starts = sorted(s for s in by_start if 0 <= s < total)
    events: list[_Event] = []
    at = Fraction(0)
    for index, start in enumerate(starts):
        group = by_start[start]
        end = min(max(n.dur for n in group) + start, total)
        if index + 1 < len(starts):
            end = min(end, starts[index + 1])
        if start > at:
            events.append(_Event(at, start - at, []))
        if end > start:
            events.append(_Event(start, end - start, sorted(group, key=lambda n: n.pitch)))
            at = end
    if at < total:
        events.append(_Event(at, total - at, []))
    return events


def to_mei(staff: Staff) -> tuple[str, int]:
    """The staff as an MEI document, and how many notes were rounded onto the grid."""
    bar_len = staff.meter.beats_per_bar
    total = bar_len * staff.bars
    rounded = 0
    notes = []
    for note in staff.notes:
        start, dur = _snap(note.start), max(_snap(note.dur), _GRID)
        if (start, dur) != (note.start, note.dur):
            rounded += 1
        notes.append(StaffNote(note.pitch, start, dur, note.id, note.color, note.voice))
    clef = staff.clef
    if clef is None:
        pitches = sorted(n.pitch for n in notes)
        clef = "F4" if pitches and pitches[len(pitches) // 2] < 57 else "G2"
    voices = sorted({n.voice for n in notes}) or [0]
    signature = _signature(staff.key)
    group = _beat_group(staff.meter)
    unit = Fraction(staff.meter.denominator, 4)  # meter beats per quarter

    # Each voice's events, cut at the barlines, as (bar index -> list of pieces)
    measures: list[list[str]] = [[] for _ in range(staff.bars)]
    for layer_n, voice in enumerate(voices, start=1):
        events = _layer_events([n for n in notes if n.voice == voice], total)
        per_bar: list[list[str]] = [[] for _ in range(staff.bars)]
        accidentals: list[dict[tuple[str, int], int]] = [{} for _ in range(staff.bars)]
        beams: list[list[tuple[Fraction, str, bool]]] = [[] for _ in range(staff.bars)]
        for event in events:
            end = event.start + event.dur
            bar = int(event.start // bar_len)
            first = True
            while bar < staff.bars and bar * bar_len < end:
                lo = max(event.start, bar * bar_len)
                hi = min(end, (bar + 1) * bar_len)
                pieces = _pieces(lo - bar * bar_len, hi - lo, bar_len, rest=not event.notes)
                at = lo
                for p_index, (value, dur, dots) in enumerate(pieces):
                    last = hi == end and p_index == len(pieces) - 1
                    xml = _event_xml(
                        event, dur, dots, first, last, staff.key, signature, accidentals[bar]
                    )
                    beamable = bool(event.notes) and value < 1
                    beams[bar].append((at - bar * bar_len, xml, beamable))
                    first = False
                    at += value
                bar += 1
        for index in range(staff.bars):
            per_bar[index] = _beamed(beams[index], group)
            measures[index].append(f'<layer n="{layer_n}">' + "".join(per_bar[index]) + "</layer>")

    body = []
    for index in range(staff.bars):
        if index and staff.bars_per_line and index % staff.bars_per_line == 0:
            body.append("<sb/>")
        harms = "".join(
            f'<harm staff="1" tstamp="{float((beat - index * bar_len) * unit + 1):g}">'
            f"{html.escape(_pretty(symbol))}</harm>"
            for beat, symbol in staff.chords
            if index * bar_len <= beat < (index + 1) * bar_len
        )
        body.append(
            f'<measure n="{staff.first_bar + index}"><staff n="1">'
            + "".join(measures[index])
            + f"</staff>{harms}</measure>"
        )
    line, shape = clef[1], clef[0]
    mei = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="5.0">'
        "<meiHead><fileDesc><titleStmt><title/></titleStmt><pubStmt/></fileDesc></meiHead>"
        "<music><body><mdiv><score>"
        f'<scoreDef meter.count="{staff.meter.numerator}" meter.unit="{staff.meter.denominator}" '
        f'key.sig="{_key_sig(staff.key)}"><staffGrp>'
        f'<staffDef n="1" lines="5" clef.shape="{shape}" clef.line="{line}"/>'
        "</staffGrp></scoreDef><section>" + "".join(body) + "</section>"
        "</score></mdiv></body></music></mei>"
    )
    return mei, rounded


def _pretty(symbol: str) -> str:
    """A chord symbol with real flat and sharp signs on its root and bass."""
    return re.sub(r"(^|/)([A-G])b", r"\1\2♭", re.sub(r"(^|/)([A-G])#", r"\1\2♯", symbol))


def _event_xml(
    event: _Event,
    dur: str,
    dots: int,
    first: bool,
    last: bool,
    key: Key,
    signature: dict[str, int],
    accidentals: dict[tuple[str, int], int],
) -> str:
    dots_attr = f' dots="{dots}"' if dots else ""
    if not event.notes:
        return f'<rest dur="{dur}"{dots_attr}/>'
    tie = None if first and last else "i" if first else "t" if last else "m"
    parts = []
    for note in event.notes:
        letter, alter, octave = spell(note.pitch, key)
        attrs = [f'pname="{letter.lower()}"', f'oct="{octave}"']
        if len(event.notes) == 1:
            attrs.append(f'dur="{dur}"')
            if dots:
                attrs.append(f'dots="{dots}"')
        current = accidentals.get((letter, octave), signature[letter])
        written = {0: "n", 1: "s", -1: "f", 2: "x", -2: "ff"}[alter]
        if alter != current and first:
            attrs.append(f'accid="{written}"')
            accidentals[(letter, octave)] = alter
        else:
            attrs.append(f'accid.ges="{written}"')
        if tie:
            attrs.append(f'tie="{tie}"')
        if note.color:
            attrs.append(f'color="{note.color}"')
        if note.id and first:
            attrs.append(f'xml:id="{_xml_id(note.id)}"')
        parts.append("<note " + " ".join(attrs) + "/>")
    if len(parts) == 1:
        return parts[0]
    return f'<chord dur="{dur}"{dots_attr}>' + "".join(parts) + "</chord>"


def _beamed(pieces: list[tuple[Fraction, str, bool]], group: Fraction) -> list[str]:
    """Pieces of one bar, with runs of short notes in the same beat put under a beam."""
    out: list[str] = []
    run: list[str] = []
    run_group: Fraction | None = None

    def close() -> None:
        if len(run) > 1:
            out.append("<beam>" + "".join(run) + "</beam>")
        else:
            out.extend(run)
        run.clear()

    for at, xml, beamable in pieces:
        beat = at // group
        if beamable and (run_group is None or beat == run_group):
            run.append(xml)
            run_group = beat
            continue
        close()
        run_group = None
        if beamable:
            run.append(xml)
            run_group = beat
        else:
            out.append(xml)
    close()
    return out


def engrave(staff: Staff, width: int = 2400) -> Engraved:
    """
    The staff as SVG, scaled to its container by its view box.

    Raises:
        RuntimeError: When Verovio is not installed (`pip install verovio`)
    """
    try:
        from importlib.resources import files

        import verovio
    except ImportError as error:
        raise RuntimeError("notation needs Verovio: pip install verovio") from error
    mei, rounded = to_mei(staff)
    # The default resource path is set for the thread that imported Verovio only,
    # and a server answers on other threads, so each toolkit is told where its
    # fonts are.
    verovio.enableLog(verovio.LOG_OFF)
    toolkit = verovio.toolkit(False)
    toolkit.setResourcePath(str(files("verovio") / "data"))
    toolkit.setOptions(
        {
            "pageWidth": width,
            "pageMarginLeft": 20,
            "pageMarginRight": 20,
            "pageMarginTop": 20,
            "pageMarginBottom": 10,
            "adjustPageHeight": True,
            "breaks": "encoded",
            "minLastJustification": 0,  # a short last line keeps the bar widths of the others
            "header": "none",
            "footer": "none",
            "scale": 40,
            "svgViewBox": True,
        }
    )
    if not toolkit.loadData(mei):
        raise RuntimeError("Verovio could not read the staff")
    svg = "".join(toolkit.renderToSVG(page) for page in range(1, toolkit.getPageCount() + 1))
    ids = {_xml_id(n.id): n.id for n in staff.notes if n.id}
    return Engraved(svg, rounded, ids)
