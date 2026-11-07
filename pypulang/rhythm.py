"""
Rhythm cells: a bar written as a string of steps.

    "x..x..x. ..x.x..."

Each character is one step. Spaces and "|" are ignored, so a cell can be grouped
for reading. The characters are:

    x   a hit
    X   an accented hit
    o   a ghost note
    -   hold the previous hit one more step
    .   nothing
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

ACCENT = Fraction(6, 5)
GHOST = Fraction(9, 20)


@dataclass(frozen=True)
class Hit:
    """One hit in a cell: where it falls, how long it rings, how hard it lands."""

    step: int
    steps: int
    weight: Fraction


def read_cell(cell: str) -> tuple[list[Hit], int]:
    """
    Parse a cell.

    Returns:
        The hits, and the cell's length in steps

    Raises:
        ValueError: On a character that is not part of the notation
    """
    hits: list[Hit] = []
    length = 0
    for char in cell:
        if char in " |\n\t":
            continue
        if char == "-":
            if hits and hits[-1].step + hits[-1].steps == length:
                last = hits[-1]
                hits[-1] = Hit(last.step, last.steps + 1, last.weight)
        elif char in "xXo":
            weight = {"x": Fraction(1), "X": ACCENT, "o": GHOST}[char]
            hits.append(Hit(length, 1, weight))
        elif char != ".":
            raise ValueError(f"Unknown rhythm character {char!r} in {cell!r}")
        length += 1
    return hits, length


def scaled_velocity(velocity: int, weight: Fraction) -> int:
    return max(1, min(127, int(velocity * weight)))
