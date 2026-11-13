"""
The companion page's song and changes views: the whole song as inputs, each with
the line that set it and a mark when an edit changed it, and folding from there.
"""

from __future__ import annotations

import pytest

from pypulang.serve import Companion

SONG = """
from pypulang import *

with piece(tempo=80, key="F minor", title="panel") as song:
    song.motif("m", "5/4 6 5 3")
    a = song.section("a", bars=2, tempo=72)
    a.chart("Fm9 | Bbm7 Eb7")
    a.track("lead", role=Role.MELODY).melody("m; m -1", low=60, high=76).velocity(90)
    b = a.transform("b")
    song.form([a, b])
"""


@pytest.fixture
def companion(tmp_path):
    path = tmp_path / "panel.py"
    path.write_text(SONG)
    return Companion(path, None)


def test_the_song_view_shows_every_value_as_an_input_with_its_line(companion):
    page = companion.page({})
    assert 'id="tab-song"' in page and 'id="tab-changes"' in page
    assert 'value="Fm9 | Bbm7 Eb7"' in page and 'value="72"' in page
    assert 'value="m; m -1"' in page and 'value="5/4 6 5 3"' in page
    assert "made from a: follows its edits" in page
    assert 'title="a = song.section(&quot;a&quot;, bars=2, tempo=72)">line 6' in page


def test_an_edited_value_says_so_and_offers_the_source_back(companion):
    companion.edit("intent", "a/lead", "velocity", "70")
    page = companion.page({})
    assert 'class="edited"' in page and 'title="the source says 90">edited' in page
    assert 'name="key" value="intent:a/lead:velocity"' in page


def test_the_changes_view_folds_into_the_source(companion):
    companion.edit("intent", "a/lead", "velocity", "70")
    preview = companion.fold_preview("/")
    assert "1 edit(s) can be written into" in preview and ".velocity(70)" in preview
    assert "Wrote 1 edit(s) into panel.py" in companion.fold()
    assert ".velocity(70)" in companion.path.read_text()
    assert "Nothing to fold" in companion.fold_preview("/")
