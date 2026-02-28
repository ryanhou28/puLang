"""
Hot reload support for pypulang.

Watches source files for changes and automatically reloads and restarts playback,
enabling rapid iteration during composition.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import os
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from pypulang.playback.protocols import PlaybackBackend, PlaybackHandle
    from pypulang.playback.instruments import InstrumentBank


class FileWatcher:
    """
    Watches a file for changes and triggers callbacks on modification.

    Uses polling (checking mtime) for simplicity and cross-platform support.
    """

    def __init__(
        self,
        file_path: str | Path,
        callback: Callable[[], None],
        poll_interval: float = 0.5,
    ) -> None:
        """
        Initialize the file watcher.

        Args:
            file_path: Path to the file to watch
            callback: Function to call when file changes
            poll_interval: How often to check for changes (seconds)
        """
        self._file_path = Path(file_path).resolve()
        self._callback = callback
        self._poll_interval = poll_interval
        self._last_mtime: float | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start watching the file for changes."""
        if self._running:
            return

        self._running = True
        self._last_mtime = self._get_mtime()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop watching the file."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _get_mtime(self) -> float | None:
        """Get the modification time of the watched file."""
        try:
            return self._file_path.stat().st_mtime
        except OSError:
            return None

    def _watch_loop(self) -> None:
        """Main watch loop that polls for changes."""
        while self._running:
            time.sleep(self._poll_interval)

            if not self._running:
                break

            current_mtime = self._get_mtime()

            if current_mtime is None:
                continue

            if self._last_mtime is not None and current_mtime > self._last_mtime:
                self._last_mtime = current_mtime
                try:
                    self._callback()
                except Exception as e:
                    print(f"[watch] Error in callback: {e}")
            elif self._last_mtime is None:
                self._last_mtime = current_mtime


class WatchHandle:
    """
    Handle for controlling hot reload watching.

    Returned by PieceBuilder.watch() to allow stopping the watch.
    """

    def __init__(
        self,
        watcher: FileWatcher,
        playback_handle: PlaybackHandle | None,
        file_path: Path,
    ) -> None:
        self._watcher = watcher
        self._playback_handle = playback_handle
        self._file_path = file_path
        self._stopped = False

    def stop(self) -> None:
        """Stop watching and stop any active playback."""
        self._stopped = True
        self._watcher.stop()
        if self._playback_handle is not None:
            self._playback_handle.stop()

    def is_watching(self) -> bool:
        """Check if still watching for changes."""
        return not self._stopped

    @property
    def file_path(self) -> Path:
        """Get the path of the watched file."""
        return self._file_path


class HotReloadSession:
    """
    Manages a hot reload session for a piece.

    Handles reloading the source module, reconstructing the piece,
    and restarting playback with position preservation.
    """

    def __init__(
        self,
        source_file: Path,
        piece_var_name: str,
        backend: "PlaybackBackend | None",
        instruments: "InstrumentBank | None",
        loop: bool,
        from_bar: int | None,
        section: str | None,
    ) -> None:
        self._source_file = source_file
        self._piece_var_name = piece_var_name
        self._backend = backend
        self._instruments = instruments
        self._loop = loop
        self._from_bar = from_bar
        self._section = section

        self._current_handle: "PlaybackHandle | None" = None
        self._watcher: FileWatcher | None = None
        self._stopped = False
        self._current_tempo: float = 120.0  # Track tempo for position calculation
        self._current_time_sig_beats: float = 4.0  # Beats per bar
        self._lock = threading.Lock()

    def start(self) -> WatchHandle:
        """Start the hot reload session."""
        # Start initial playback
        self._start_playback()

        # Start watching for changes
        self._watcher = FileWatcher(
            self._source_file,
            callback=self._on_file_change,
        )
        self._watcher.start()

        print(f"[watch] Watching {self._source_file.name} for changes...")
        print("[watch] Press Ctrl+C to stop")

        return WatchHandle(self._watcher, self._current_handle, self._source_file)

    def stop(self) -> None:
        """Stop the hot reload session."""
        self._stopped = True
        if self._watcher is not None:
            self._watcher.stop()
        if self._current_handle is not None:
            self._current_handle.stop()

    def _start_playback(self, from_bar: int | None = None) -> None:
        """Start playback of the current piece."""
        from pypulang.playback.config import get_default_backend

        # Load the piece from the source file
        piece_builder = self._load_piece()
        if piece_builder is None:
            print("[watch] Failed to load piece, skipping playback")
            return

        # Get backend
        backend = self._backend
        if backend is None:
            backend = get_default_backend()

        # Start playback
        start_bar = from_bar if from_bar is not None else self._from_bar

        with self._lock:
            # Track tempo and time signature for position calculations
            self._current_tempo = piece_builder._tempo
            self._current_time_sig_beats = float(piece_builder._time_signature.numerator)

            if self._loop:
                self._current_handle = piece_builder.loop(
                    backend=backend,
                    instruments=self._instruments,
                    section=self._section,
                )
            else:
                self._current_handle = piece_builder.play(
                    backend=backend,
                    instruments=self._instruments,
                    from_bar=start_bar,
                    section=self._section,
                    wait=False,
                )

    def _load_piece(self) -> Any:
        """Load and return the piece from the source file."""
        try:
            # Create a module spec for the source file
            module_name = self._source_file.stem
            spec = importlib.util.spec_from_file_location(
                module_name,
                self._source_file
            )

            if spec is None or spec.loader is None:
                print(f"[watch] Could not load module spec for {self._source_file}")
                return None

            # Check if module is already loaded
            if module_name in sys.modules:
                # Reload the module
                module = sys.modules[module_name]
                module = importlib.reload(module)
            else:
                # Load the module for the first time
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

            # Get the piece variable
            if hasattr(module, self._piece_var_name):
                return getattr(module, self._piece_var_name)
            else:
                # Try to find a PieceBuilder instance
                from pypulang.dsl import PieceBuilder
                for name, obj in vars(module).items():
                    if isinstance(obj, PieceBuilder):
                        return obj

                print(f"[watch] Could not find piece '{self._piece_var_name}' in module")
                return None

        except Exception as e:
            print(f"[watch] Error loading piece: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_current_bar(self) -> int | None:
        """
        Get the current playback position as a bar number (best effort).

        Returns:
            Current bar number (1-indexed) or None if can't determine
        """
        with self._lock:
            if self._current_handle is None:
                return None

            # Try to get position from handle
            try:
                if hasattr(self._current_handle, 'get_position_beats'):
                    beats = self._current_handle.get_position_beats(self._current_tempo)
                    bar = int(beats / self._current_time_sig_beats) + 1
                    return bar
            except Exception:
                pass

            return None

    def _on_file_change(self) -> None:
        """Called when the watched file changes."""
        if self._stopped:
            return

        print(f"\n[watch] File changed, reloading...")

        # Calculate current playback position (best effort)
        current_bar = self._get_current_bar()
        if current_bar is not None:
            print(f"[watch] Preserving position: bar {current_bar}")

        # Stop current playback
        with self._lock:
            if self._current_handle is not None:
                self._current_handle.stop()
                self._current_handle = None

        # Small delay to let the file system settle
        time.sleep(0.1)

        # Restart playback
        self._start_playback(from_bar=current_bar)
        print("[watch] Playback restarted")


def get_caller_file() -> Path | None:
    """
    Get the source file of the caller (outside of pypulang package).

    Walks up the call stack to find the first frame outside of pypulang.
    """
    pypulang_path = Path(__file__).parent.parent.resolve()

    for frame_info in inspect.stack():
        frame_path = Path(frame_info.filename).resolve()

        # Skip frames inside pypulang package
        try:
            frame_path.relative_to(pypulang_path)
            continue
        except ValueError:
            # Not inside pypulang, this is the caller
            if frame_path.exists() and frame_path.suffix == ".py":
                return frame_path

    return None


def watch_piece(
    piece_builder: Any,
    source_file: str | Path | None = None,
    piece_var: str = "p",
    backend: "PlaybackBackend | None" = None,
    instruments: "InstrumentBank | None" = None,
    loop: bool = True,
    from_bar: int | None = None,
    section: str | None = None,
) -> WatchHandle:
    """
    Start watching a source file and hot-reload on changes.

    Args:
        piece_builder: The PieceBuilder instance to watch
        source_file: Path to the source file to watch (auto-detected if None)
        piece_var: Variable name of the piece in the source file
        backend: Playback backend to use
        instruments: InstrumentBank for custom instruments
        loop: Whether to loop playback (default True)
        from_bar: Starting bar for playback
        section: Specific section to play

    Returns:
        WatchHandle for controlling the watch session

    Example:
        from pypulang import piece, I, IV, vi, V, Role, root_quarters

        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters)

        # Watch this file for changes
        p.watch()  # Loops playback and reloads on save
    """
    # Determine source file to watch
    if source_file is None:
        source_file = get_caller_file()
        if source_file is None:
            raise RuntimeError(
                "Could not auto-detect source file. "
                "Please pass the source_file parameter explicitly."
            )
    else:
        source_file = Path(source_file).resolve()

    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")

    # Create and start the hot reload session
    session = HotReloadSession(
        source_file=source_file,
        piece_var_name=piece_var,
        backend=backend,
        instruments=instruments,
        loop=loop,
        from_bar=from_bar,
        section=section,
    )

    return session.start()
