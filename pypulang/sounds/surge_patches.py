"""
Surge XT patches as plugin state.

Surge reports no programs to its host, so kaiDAW's `LoadPluginPreset` cannot pick
one of its patches. kaiDAW's `RestorePluginState` can: it takes a plugin's whole
state, which for a VST3 hosted by JUCE (kaiDAW is one) is this envelope:

    magic 0x21324356, little-endian length, then XML:
    <VST3PluginState><IComponent>JUCE-base64 of the component state</IComponent>

Surge's component state is its raw patch: the bytes after the 60-byte header of a
`.fxp` file. Both facts were read off a running Surge XT 1.3 through kaiDAW on
2026-11-07, not assumed: a state read from the plugin decodes to `sub3...`, and a
factory patch wrapped this way loads.

JUCE's base64 is not RFC 4648. It is the byte count, a dot, then 6-bit groups
taken least-significant bit first, with its own alphabet. Standard base64 in the
XML would decode to garbage without an error.
"""

from __future__ import annotations

import base64
import os
import struct
from pathlib import Path

_JUCE_TABLE = ".ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+"
_JUCE_INDEX = {ch: i for i, ch in enumerate(_JUCE_TABLE)}
_XML_MAGIC = 0x21324356
_FXP_HEADER = 60


def juce_base64(data: bytes) -> str:
    """Encode bytes the way `juce::MemoryBlock::toBase64Encoding` does."""
    bits = int.from_bytes(data, "little")
    count = (len(data) * 8 + 5) // 6
    return f"{len(data)}." + "".join(_JUCE_TABLE[(bits >> (6 * i)) & 63] for i in range(count))


def from_juce_base64(text: str) -> bytes:
    """Decode `juce::MemoryBlock::fromBase64Encoding`'s format."""
    size, dot, chars = text.partition(".")
    if not dot:
        raise ValueError("not JUCE base64: no length prefix")
    length = int(size)
    bits = 0
    for i, ch in enumerate(chars):
        bits |= _JUCE_INDEX.get(ch, 0) << (6 * i)
    return (bits & ((1 << (8 * length)) - 1)).to_bytes(length, "little")


def patch_from_fxp(fxp: bytes) -> bytes:
    """
    The raw patch inside a Surge `.fxp` file.

    Raises:
        ValueError: If this is not a Surge patch file
    """
    if len(fxp) < _FXP_HEADER or fxp[:4] != b"CcnK" or fxp[8:12] != b"FPCh":
        raise ValueError("not an .fxp chunk file")
    if fxp[16:20] != b"cjs3":
        raise ValueError(f"an .fxp for another plugin ({fxp[16:20]!r}), not Surge")
    (size,) = struct.unpack(">I", fxp[56:60])
    raw = fxp[_FXP_HEADER : _FXP_HEADER + size]
    if len(raw) != size or raw[:4] != b"sub3":
        raise ValueError("truncated or unrecognised Surge patch")
    return raw


def vst3_state(component: bytes) -> str:
    """A component state wrapped as kaiDAW's `RestorePluginState` takes it, base64."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?> <VST3PluginState><IComponent>'
        + juce_base64(component)
        + "</IComponent></VST3PluginState>"
    ).encode()
    return base64.b64encode(struct.pack("<II", _XML_MAGIC, len(xml)) + xml + b"\0").decode()


def component_of(state: str) -> bytes:
    """The component state inside a state from kaiDAW's `GET /plugin/state`."""
    blob = base64.b64decode(state)
    magic, length = struct.unpack("<II", blob[:8])
    if magic != _XML_MAGIC:
        raise ValueError("not a JUCE-hosted VST3 state")
    xml = blob[8 : 8 + length].decode()
    start = xml.index("<IComponent>") + len("<IComponent>")
    return from_juce_base64(xml[start : xml.index("</IComponent>")])


def factory_dirs() -> list[Path]:
    """Where Surge XT installs its factory patches, most specific first."""
    dirs = []
    if os.environ.get("SURGE_PATCHES"):
        dirs.append(Path(os.environ["SURGE_PATCHES"]))
    dirs += [
        Path("/mnt/c/ProgramData/Surge XT/patches_factory"),  # Windows, seen from WSL
        Path("C:/ProgramData/Surge XT/patches_factory"),
        Path("/usr/share/surge-xt/patches_factory"),
        Path("/Library/Application Support/Surge XT/patches_factory"),
    ]
    return [d for d in dirs if d.is_dir()]


def find_patch(name: str) -> Path:
    """
    A factory patch by its category and name, such as "Keys/Artificial 1".

    Raises:
        FileNotFoundError: Naming the places looked, if it is not there
    """
    looked = factory_dirs()
    for directory in looked:
        path = directory / f"{name}.fxp"
        if path.is_file():
            return path
    where = ", ".join(str(d) for d in looked) or "no Surge XT patch folder found; set SURGE_PATCHES"
    raise FileNotFoundError(f"no Surge patch {name!r} in {where}")


def patch_state(name: str) -> str:
    """A factory patch as plugin state for kaiDAW, base64."""
    return vst3_state(patch_from_fxp(find_patch(name).read_bytes()))
