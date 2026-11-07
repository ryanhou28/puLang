"""
The puLang compiler: dialects, lowerings, and passes built on xDSL.

    Piece -> intent -> score -> event -> daw

`compile_piece` runs the whole pipeline. Each level is an ordinary xDSL module,
so it can be printed, parsed back, verified, and rewritten by a pass.
"""

from __future__ import annotations

from pypulang.compiler.pipeline import (
    CompileResult,
    compile_piece,
    make_context,
    parse_ir,
    print_ir,
)

__all__ = ["CompileResult", "compile_piece", "make_context", "parse_ir", "print_ir"]
