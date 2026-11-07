"""
Analysis of the `score` dialect: questions about the music itself.

This is where the compiler can review its own output. It cannot say a line is
beautiful, but it can say a held note sits a semitone above the chord it is played
over, which is usually a mistake and always worth a look.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from fractions import Fraction

from xdsl.dialects.builtin import ModuleOp

from pypulang.compiler.dialects import score
from pypulang.compiler.locs import loc_key
from pypulang.compiler.spelling import midi_of
from pypulang.harmony import chord_shape, chord_symbol
from pypulang.scales import get_scale_pitches, pitch_class_to_semitone

# Long enough to be heard as a statement rather than passed through.
HELD = Fraction(1)


@dataclass
class Finding:
    kind: str
    location: str
    message: str


@dataclass
class Review:
    """What a read-through of the score found."""

    findings: list[Finding] = field(default_factory=list)
    chord_tones: int = 0
    tensions: int = 0
    scale_tones: int = 0
    outside: int = 0

    @property
    def strong_notes(self) -> int:
        return self.chord_tones + self.tensions + self.scale_tones + self.outside

    def summary(self) -> str:
        lines = []
        total = self.strong_notes or 1
        lines.append(
            f"Strong-beat melody notes: {self.chord_tones * 100 // total}% chord tones, "
            f"{self.tensions * 100 // total}% tensions, {self.scale_tones * 100 // total}% "
            f"scale tones, {self.outside * 100 // total}% outside ({self.strong_notes} notes)"
        )
        by_kind: dict[str, int] = {}
        for finding in self.findings:
            by_kind[finding.kind] = by_kind.get(finding.kind, 0) + 1
        for kind, count in sorted(by_kind.items()):
            lines.append(f"{count} {kind}")
        lines.extend(f"  {f.kind} at {f.location}: {f.message}" for f in self.findings[:40])
        return "\n".join(lines)


class _ChordLookup:
    def __init__(self, chords: list[score.ChordOp]):
        self.chords = sorted(chords, key=lambda c: c.at.data)
        self.starts = [c.at.data for c in self.chords]

    def at(self, time: Fraction) -> score.ChordOp | None:
        index = bisect_right(self.starts, time) - 1
        if index < 0:
            return None
        chord = self.chords[index]
        return chord if time < chord.at.data + chord.dur.data else None


def _review_note(note: score.NoteOp, time: Fraction, chord: score.ChordOp, review: Review) -> None:
    shape = chord_shape(chord.chord.data, chord.key.data)
    pc = midi_of(note.pitch.data) % 12
    tones = {shape.pitch_class(t): t for t in shape.tones}
    core = {
        shape.pitch_class(t)
        for t in shape.tones
        if t.function in ("1", "3", "5", "b5", "#5", "7", "6", "4", "2")
    }
    name = chord_symbol(chord.chord.data, chord.key.data)
    if pc in tones:
        function = tones[pc].function
        if function in ("9", "b9", "#9", "11", "#11", "13", "b13"):
            review.tensions += 1
        else:
            review.chord_tones += 1
        return

    root = pitch_class_to_semitone(chord.key.data.root)
    scale = {(root + s) % 12 for s in get_scale_pitches(chord.key.data)}
    if pc in scale:
        review.scale_tones += 1
    else:
        review.outside += 1

    # A semitone above a chord tone is the classic clash: F held over a C major chord.
    rubs = (pc - 1) % 12 in core
    if rubs and note.dur.data >= HELD:
        review.findings.append(
            Finding(
                "clash",
                loc_key(note.location),
                f"{note.pitch.data} for {note.dur.data} beats, a semitone above a tone of {name}",
            )
        )


def _strong(beat: Fraction) -> bool:
    return beat.denominator == 1


def review_melodies(top: score.ScoreOp, review: Review) -> None:
    chords = _ChordLookup(top.chords())
    for part in top.parts():
        if part.role.data != "melody":
            continue
        for bar in part.bars():
            for note in bar.notes():
                time = bar.start.data + note.beat.data
                if not _strong(note.beat.data) and note.dur.data < HELD:
                    continue
                chord = chords.at(time)
                if chord is not None:
                    _review_note(note, time, chord, review)


def review_ranges(top: score.ScoreOp, review: Review) -> None:
    """Bass under E1 is mud and melody over C7 is a dog whistle."""
    limits = {"bass": (24, 67), "melody": (48, 100), "harmony": (36, 103)}
    for part in top.parts():
        low, high = limits.get(part.role.data, (0, 127))
        for bar in part.bars():
            for note in bar.notes():
                pitch = midi_of(note.pitch.data)
                if not low <= pitch <= high:
                    review.findings.append(
                        Finding(
                            "out of range",
                            loc_key(note.location),
                            f"{note.pitch.data} on {part.role.data} track {part.part.data}",
                        )
                    )


def review_parallels(top: score.ScoreOp, review: Review) -> None:
    """Consecutive fifths and octaves between voices of a harmony part."""
    for part in top.parts():
        if part.role.data != "harmony":
            continue
        onsets: dict[Fraction, list[int]] = {}
        for bar in part.bars():
            for note in bar.notes():
                time = bar.start.data + note.beat.data
                onsets.setdefault(time, []).append(midi_of(note.pitch.data))
        times = sorted(onsets)
        for first, second in zip(times, times[1:], strict=False):
            a, b = sorted(onsets[first]), sorted(onsets[second])
            if len(a) != len(b) or a == b:
                continue
            for i in range(len(a)):
                for j in range(i + 1, len(a)):
                    interval = (a[j] - a[i]) % 12
                    moved = b[i] - a[i]
                    if (
                        interval in (0, 7)
                        and moved
                        and (b[j] - b[i]) % 12 == interval
                        and b[j] - a[j] == moved
                    ):
                        review.findings.append(
                            Finding(
                                "parallel",
                                f"{part.part.data} beat {float(first):.2f}",
                                f"{'octaves' if interval == 0 else 'fifths'} moving by {moved}",
                            )
                        )


def review(module: ModuleOp) -> Review:
    """Read through a realized `score` module."""
    result = Review()
    for top in module.body.block.ops:
        if isinstance(top, score.ScoreOp):
            review_melodies(top, result)
            review_ranges(top, result)
            review_parallels(top, result)
    return result
