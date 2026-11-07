"""The HTTP client, and how to reach a server from wherever puLang is running."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol

DEFAULT_PORT = 8899


class KaidawError(RuntimeError):
    """The server refused a request, or could not be reached."""


class Transport(Protocol):
    def request(self, method: str, path: str, body: Any = None) -> Any: ...


class HttpTransport:
    """Plain HTTP, for when the server is on this machine."""

    def __init__(self, port: int = DEFAULT_PORT, host: str = "127.0.0.1", timeout: float = 120):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout

    def request(self, method: str, path: str, body: Any = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            # A rejected command arrives as a 4xx with the reason in its body.
            raw = error.read()
        except OSError as error:
            raise KaidawError(f"Cannot reach kaiDAW at {self.base}: {error}") from error
        return json.loads(raw) if raw else {}


class WslTransport:
    """
    Reach a Windows-hosted server from WSL2.

    The server binds 127.0.0.1 and WSL2 is NAT'd, so WSL's localhost is a different
    machine. This hops through Windows' own curl, with payloads passed by file so
    no JSON goes through cmd.exe's quoting. It mirrors kaiDAW's tools/daw.sh.

    Launching a Windows process from WSL occasionally fails before the process
    runs, which shows up as exit status 1. curl itself cannot exit 1 here, so that
    status means nothing reached the server and retrying is safe.
    """

    ATTEMPTS = 5

    def __init__(
        self,
        port: int = DEFAULT_PORT,
        share_wsl: str | None = None,
        share_win: str | None = None,
        timeout: float = 120,
    ):
        self.port = port
        self.timeout = timeout
        self.share_wsl = (
            Path(share_wsl or os.environ.get("KAIDAW_WIN_DIR", "/mnt/c/kaidaw-win")) / "tmp"
        )
        self.share_win = (
            share_win or os.environ.get("KAIDAW_WIN_PATH", "C:\\kaidaw-win")
        ) + "\\tmp"

    def _curl(self, args: list[str]) -> bytes:
        command = ["curl.exe", "-s", "-m", str(int(self.timeout)), *args]
        for attempt in range(self.ATTEMPTS):
            result = subprocess.run(
                command, cwd=self.share_wsl, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            if result.returncode == 0:
                return result.stdout
            if result.returncode != 1:
                raise KaidawError(
                    f"curl.exe exited {result.returncode}: is kaiDAW running on port {self.port}?"
                )
            time.sleep(1 + attempt)
        raise KaidawError(f"Could not launch curl.exe after {self.ATTEMPTS} attempts")

    def request(self, method: str, path: str, body: Any = None) -> Any:
        url = f"http://127.0.0.1:{self.port}{path}"
        if method == "GET":
            raw = self._curl([url])
        else:
            self.share_wsl.mkdir(parents=True, exist_ok=True)
            name = f"pulang-{os.getpid()}.json"
            payload = self.share_wsl / name
            payload.write_text(json.dumps(body if body is not None else {}))
            try:
                raw = self._curl(
                    [
                        "-X",
                        method,
                        url,
                        "-H",
                        "content-type: application/json",
                        "-d",
                        f"@{self.share_win}\\{name}",
                    ]
                )
            finally:
                payload.unlink(missing_ok=True)
        return json.loads(raw) if raw else {}


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def default_transport(port: int = DEFAULT_PORT) -> Transport:
    """HTTP, unless this is WSL and the server is only reachable from Windows."""
    direct = HttpTransport(port, timeout=2)
    try:
        direct.request("GET", "/health")
        return HttpTransport(port)
    except KaidawError:
        if _is_wsl():
            return WslTransport(port)
        raise


class KaidawClient:
    """The operations puLang needs from a kaiDAW server."""

    def __init__(self, transport: Transport | None = None, port: int = DEFAULT_PORT):
        self.transport = transport if transport is not None else default_transport(port)

    def health(self) -> dict[str, Any]:
        return self.transport.request("GET", "/health")

    def projection(self, level: str = "detail") -> dict[str, Any]:
        return self.transport.request("GET", f"/projection?level={level}")

    def revision(self) -> int:
        return self.projection("summary")["revision"]

    def apply(
        self, operations: list[dict[str, Any]], base_revision: int, description: str
    ) -> dict[str, Any]:
        """
        Send one atomic transaction.

        Raises:
            KaidawError: If the engine refused it. Nothing changed in that case.
        """
        result = self.transport.request(
            "POST",
            "/apply",
            {
                "baseRevision": base_revision,
                "description": description,
                "operations": operations,
            },
        )
        if result.get("status") not in ("applied", "no_effect"):
            raise KaidawError(
                f"{result.get('status')}: {result.get('errors') or result.get('scopeViolations')}"
            )
        return result

    def plugins(self) -> list[dict[str, Any]]:
        return self.transport.request("GET", "/plugins")["plugins"]

    def undo(self) -> dict[str, Any]:
        return self.transport.request("POST", "/undo", {})

    def save(self, path: str) -> dict[str, Any]:
        return self._store("/save", path)

    def open(self, path: str) -> dict[str, Any]:
        return self._store("/open", path)

    def _store(self, endpoint: str, path: str) -> dict[str, Any]:
        result = self.transport.request("POST", endpoint, {"path": path})
        if result.get("ok") is False:
            raise KaidawError(f"{endpoint} failed: {result.get('errors')}")
        return result

    def flush_plugins(self) -> None:
        """
        Let plugins act on pending changes by running a moment of audio through them.

        Surge XT applies a change of oscillator or filter type on its next audio block,
        and at that point resets the parameters that belong to it. With no audio device
        running, that block does not come until the first render, so parameters written
        before then are silently wiped. This forces the block to happen.
        """
        if isinstance(self.transport, WslTransport):
            name = f"pulang-flush-{os.getpid()}.wav"
            self.render(f"{self.transport.share_win}\\{name}", 0.0, 0.05)
            (self.transport.share_wsl / name).unlink(missing_ok=True)
        elif isinstance(self.transport, HttpTransport):
            with tempfile.TemporaryDirectory() as directory:
                self.render(str(Path(directory) / "flush.wav"), 0.0, 0.05)
        else:
            self.transport.request("POST", "/flush", {})

    def render(
        self, path: str, start: float, length: float, timeout_ms: int = 600000
    ) -> dict[str, Any]:
        """Bounce `length` seconds from `start` to a WAV at a path the server can write."""
        result = self.transport.request(
            "POST",
            "/render",
            {"path": path, "start": start, "length": length, "timeoutMs": timeout_ms},
        )
        if not result.get("ok"):
            raise KaidawError(f"render failed: {result.get('errors')}")
        return result
