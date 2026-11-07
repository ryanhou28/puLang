"""The examples in the docs have to run, because docs here have gone stale before."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pypulang.cli import main
from pypulang.compiler import compile_piece, parse_ir
from pypulang.songfile import load_song

ROOT = Path(__file__).parent.parent


def blocks(path: str, language: str) -> list[str]:
    text = (ROOT / path).read_text()
    return re.findall(rf"```{language}\n(.*?)```", text, re.DOTALL)


@pytest.mark.parametrize(
    "source", blocks("README.md", "python")[:1] + blocks("docs/compiler.md", "python")
)
def test_python_examples_compile(source, tmp_path):
    song = tmp_path / "song.py"
    song.write_text(source)
    result = load_song(song).compile()
    assert result.warnings == []


@pytest.mark.parametrize("source", blocks("docs/compiler.md", "mlir"))
def test_hand_written_ir_examples_compile(source):
    module = parse_ir(source)
    assert "daw" in compile_piece(module).stages


@pytest.mark.parametrize("song", sorted((ROOT / "examples" / "songs").glob("*.py")))
def test_the_songs_compile_and_pass_review(song, capsys):
    assert main(["check", str(song)]) == 0
    out = capsys.readouterr().out
    assert "clash" not in out
    assert "out of range" not in out
