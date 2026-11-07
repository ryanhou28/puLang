"""
Loading a song.

A song is a Python file that builds a piece, or a text file of `intent` IR.

    # song.py
    from pypulang import *

    with piece(tempo=120, key="D dorian") as p:
        ...

    # Optional: what to run at each stage of the compiler
    pipeline = {"event": [Swing(tracks=("drums",))]}
"""

from __future__ import annotations

import runpy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass

from pypulang.compiler import CompileResult, compile_piece, parse_ir
from pypulang.dsl import PieceBuilder
from pypulang.ir.intent import Piece


@dataclass
class Song:
    """What a song file defines."""

    path: Path
    source: Piece | str
    pipeline: dict[str, list[ModulePass]] = field(default_factory=dict)

    def module_or_piece(self) -> Piece | ModuleOp:
        return parse_ir(self.source) if isinstance(self.source, str) else self.source

    def compile(self, until: str = "daw", keep_trace: bool = False) -> CompileResult:
        return compile_piece(
            self.module_or_piece(),
            until=until,
            intent_passes=self.pipeline.get("intent", ()),
            score_passes=self.pipeline.get("score", ()),
            event_passes=self.pipeline.get("event", ()),
            daw_passes=self.pipeline.get("daw", ()),
            keep_trace=keep_trace,
        )


def _find_piece(namespace: dict[str, Any], path: Path) -> Piece:
    builders = [
        v for k, v in namespace.items() if isinstance(v, PieceBuilder) and not k.startswith("_")
    ]
    if "song" in namespace and isinstance(namespace["song"], PieceBuilder):
        return namespace["song"].to_ir()
    if len(builders) == 1:
        return builders[0].to_ir()
    if "song" in namespace and callable(namespace["song"]):
        built = namespace["song"]()
        return built.to_ir() if isinstance(built, PieceBuilder) else built
    raise ValueError(
        f"{path}: expected one piece, or a variable or function named `song`. "
        f"Found {len(builders)} pieces."
    )


def load_song(path: str | Path) -> Song:
    """Load a `.py` song or a text IR file."""
    file = Path(path)
    if file.suffix == ".py":
        namespace = runpy.run_path(str(file))
        return Song(file, _find_piece(namespace, file), namespace.get("pipeline", {}))
    return Song(file, file.read_text())
