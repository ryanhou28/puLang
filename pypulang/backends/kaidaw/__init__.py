"""
kaiDAW as a compiler target.

puLang is an ordinary client of kaiDAW's documented HTTP protocol. It links
nothing from kaiDAW, and it never asks the engine to understand music: everything
reaches it as notes, clips, plugins and automation.
"""

from __future__ import annotations

from pypulang.backends.kaidaw.client import KaidawClient, KaidawError
from pypulang.backends.kaidaw.state import Lock, Overrides, SongState
from pypulang.backends.kaidaw.sync import SyncReport, pull, push, status

__all__ = [
    "KaidawClient",
    "KaidawError",
    "Lock",
    "Overrides",
    "SongState",
    "SyncReport",
    "pull",
    "push",
    "status",
]
