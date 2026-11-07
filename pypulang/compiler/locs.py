"""
Source locations.

Every note carries a location saying which part of the source produced it, and
that location is its identity across recompiles. It names a musical position:

    verse#2 / keys / bar 3, beat 1/2, voice 1

A position survives what a chord index would not. Substituting a chord, or adding
one earlier in the section, leaves every later note where it was, so an edit made
in a DAW stays attached to the note it was made on.

In MLIR terms a note's location is `callsite(<place in the section> at <occurrence
in the form>)`, because a section played twice is one source with two call sites.
"""

from __future__ import annotations

from fractions import Fraction

from xdsl.dialects.builtin import CallSiteLoc, FusedLoc, NameLoc, NoneAttr, StringAttr, UnknownLoc
from xdsl.ir import Attribute

from pypulang.compiler.dialects.mus import format_rational


def name_loc(text: str) -> NameLoc:
    return NameLoc(StringAttr(text), NoneAttr())


def section_tag(section: str, occurrence: int) -> str:
    """The name of one occurrence of a section, such as "verse#2"."""
    return f"{section}#{occurrence}"


def in_section(place: str, section: str, occurrence: int) -> CallSiteLoc:
    """A location inside one occurrence of a section."""
    return CallSiteLoc(name_loc(place), name_loc(f"form/{section_tag(section, occurrence)}"))


def note_place(section: str, track: str, bar: int, beat: Fraction, voice: str) -> str:
    """
    The part of a note's location that names its place in the section.

    Args:
        section: Section name
        track: Track name
        bar: Bar within the section, counted from 1
        beat: Quarter notes from the start of that bar
        voice: "v0", "v1", ... or "d36" for a drum lane
    """
    return f"{section}/{track}/{bar}+{format_rational(beat)}/{voice}"


def loc_key(location: Attribute) -> str:
    """
    A location as one string, for lock files and overrides.

    "verse/keys/3+1/2/v1" at "form/verse#2" becomes "verse#2/keys/3+1/2/v1".
    """
    if isinstance(location, CallSiteLoc):
        callee = loc_key(location.callee)
        caller = loc_key(location.caller)
        tag = caller.removeprefix("form/")
        head, _, tail = callee.partition("/")
        if tag.partition("#")[0] == head:
            return f"{tag}/{tail}"
        return f"{callee}@{tag}"
    if isinstance(location, NameLoc):
        return location.desc.data
    if isinstance(location, FusedLoc):
        return "+".join(loc_key(loc) for loc in location.locations.data)
    if isinstance(location, UnknownLoc):
        return ""
    raise ValueError(f"Not a location the compiler makes: {location}")
