"""
Transforms on the `intent` dialect.

Harmony is an SSA value that tracks point at, so rewriting one `intent.harmony` op
changes what every track in that section plays. Nothing else has to be told.
"""

from __future__ import annotations

from dataclasses import dataclass

from xdsl.context import Context
from xdsl.dialects.builtin import ArrayAttr, IntegerAttr, ModuleOp, i64
from xdsl.passes import ModulePass

from pypulang.compiler.dialects import intent
from pypulang.compiler.dialects.mus import ChordAttr, KeyAttr, RationalAttr
from pypulang.ir.intent import ChordChange
from pypulang.reharm import reharmonize, transposed_key


def _piece(module: ModuleOp) -> intent.PieceOp:
    return next(o for o in module.body.block.ops if isinstance(o, intent.PieceOp))


@dataclass(frozen=True)
class Reharmonize(ModulePass):
    """
    Rewrite the harmony of some sections.

    Args:
        strategy: tritone_sub, jazzify, modal_interchange, or secondary_dominants
        sections: Which sections (default all)
    """

    name = "reharmonize"
    strategy: str = "jazzify"
    sections: tuple[str, ...] = ()

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        piece = _piece(op)
        for section in piece.sections():
            if self.sections and section.section.data not in self.sections:
                continue
            harmony = section.harmony()
            if harmony is None:
                continue
            key = section.key.data if section.key is not None else piece.key.data
            changes = [ChordChange(c, d) for c, d in harmony.changes()]
            rewritten = reharmonize(changes, key, self.strategy)
            harmony.properties["chords"] = ArrayAttr([ChordAttr(c.chord) for c in rewritten])
            harmony.properties["durations"] = ArrayAttr(
                [RationalAttr(c.duration) for c in rewritten]
            )


@dataclass(frozen=True)
class Transpose(ModulePass):
    """
    Move a piece to another key.

    Chords are numerals, so they follow the key by themselves. Only keys and literal
    notes need touching, which is the point of writing harmony as numerals.
    """

    name = "transpose"
    semitones: int = 0

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        piece = _piece(op)
        piece.properties["key"] = KeyAttr(transposed_key(piece.key.data, self.semitones))
        for section in piece.sections():
            if section.key is not None:
                section.properties["key"] = KeyAttr(
                    transposed_key(section.key.data, self.semitones)
                )
            for track in section.tracks():
                if track.role.data == "rhythm":
                    continue
                for content in track.body.block.ops:
                    if isinstance(content, intent.NotesOp):
                        for note in content.body.block.ops:
                            note.properties["pitch"] = IntegerAttr(
                                note.pitch.value.data + self.semitones, i64
                            )
