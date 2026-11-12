"""
Drum fills: what a drummer plays at the end of a phrase instead of keeping time.

A fill takes the last beats of a section, or of every few bars, from the drum
tracks: the tracks that keep time go quiet there, and the fill's own cells play
on the tracks it names. Cells are in the notation of `pypulang.rhythm`, one step
per sixteenth unless a fill says otherwise.

    chorus.fill("tom run", beats=2, keep=("pedal",))
    verse.fill("setup", beats=1, every=4)
    bridge.fill({"snare": "o.o.oxxX", "kick": "x......x"}, beats=2)

The named fills size themselves to however many beats they are given, and name
lanes as track names: "snare", "kick", "tom_high", "tom_low", "crash".

    snare roll   sixteenths on the snare, ghosted, rising to an accent
    tom run      snare, then high tom, then low tom, down the kit
    setup        the band's cue: kick and snare on the last two offbeats
    stop         one hit on the first step, then silence: the break before a section
"""

from __future__ import annotations

from collections.abc import Callable


def _snare_roll(steps: int) -> dict[str, str]:
    accents = min(4, steps)
    return {
        "snare": "o" * (steps - accents) + "x" * (accents - 1) + "X",
        "kick": "x" + "." * (steps - 1),
    }


def _tom_run(steps: int) -> dict[str, str]:
    third = max(1, steps // 3)
    lanes = {"snare": ["."] * steps, "tom_high": ["."] * steps, "tom_low": ["."] * steps}
    for index in range(steps):
        lane = "snare" if index < third else "tom_high" if index < 2 * third else "tom_low"
        lanes[lane][index] = "x"
    lanes["tom_low"][-1] = "X"
    kick = ["."] * steps
    kick[-1] = "x"
    return {**{name: "".join(cells) for name, cells in lanes.items()}, "kick": "".join(kick)}


def _setup(steps: int) -> dict[str, str]:
    snare, kick = ["."] * steps, ["."] * steps
    if steps >= 4:
        snare[-6 if steps >= 8 else -2] = "x"
        kick[-2] = "X"
    else:
        kick[-1] = "X"
    return {"snare": "".join(snare), "kick": "".join(kick)}


def _stop(steps: int) -> dict[str, str]:
    return {
        "snare": "X" + "." * (steps - 1),
        "kick": "x" + "." * (steps - 1),
        "crash": "x" + "." * (steps - 1),
    }


FILLS: dict[str, Callable[[int], dict[str, str]]] = {
    "snare roll": _snare_roll,
    "tom run": _tom_run,
    "setup": _setup,
    "stop": _stop,
}


def fill_cells(name: str, steps: int) -> dict[str, str]:
    """A named fill's cells, one per lane, `steps` steps long."""
    if name not in FILLS:
        raise ValueError(f"No fill called {name!r}; there are {', '.join(FILLS)}")
    if steps < 1:
        raise ValueError("A fill needs at least one step")
    return FILLS[name](steps)
