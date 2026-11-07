"""
Styles: patterns and voicings that encode how a kind of music goes.

Importing this package registers everything. Nothing here is special to the
compiler: a style is ordinary patterns and passes, and a song can bring its own.
"""

from __future__ import annotations

from pypulang.styles import edm, jazz

__all__ = ["edm", "jazz"]
