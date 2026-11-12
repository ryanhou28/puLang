"""
Sampled instruments: zone maps over kaiDAW's sampler.

The samples themselves are built by a script and not in the repository, so these
check the maps: every key in an instrument's range plays the nearest sample, and
no sampler holds more sounds than kaiDAW takes.
"""

from __future__ import annotations

import pytest

from pypulang.sounds.instruments import INSTRUMENTS, sampled, zones


@pytest.mark.parametrize("name", list(INSTRUMENTS))
def test_zones_cover_the_range_without_gaps_or_overlaps(name):
    found = zones(name)
    assert len(found) <= 64  # kaiDAW's limit for one sampler
    for (root, low, high), following in zip(found, found[1:] + [None], strict=True):
        assert low <= root <= high
        if following is not None:
            assert following[1] == high + 1


@pytest.mark.parametrize("name", list(INSTRUMENTS))
def test_each_key_plays_its_nearest_sample(name):
    roots = INSTRUMENTS[name].roots()
    for root, low, high in zones(name):
        for key in range(max(low, roots[0]), min(high, roots[-1]) + 1):
            assert abs(key - root) == min(abs(key - r) for r in roots) or abs(key - root) <= 1


def test_a_sampled_instrument_is_a_sampler_with_one_file_per_root():
    device = sampled("keys", "piano", folder="samples/instruments")
    assert device.identifier == "sampler"
    assert [s["file"] for s in device.sounds][:2] == [
        "samples/instruments/piano/22.wav",
        "samples/instruments/piano/24.wav",
    ]
    assert not any(s["one_shot"] for s in device.sounds)
    assert all(s["one_shot"] for s in sampled("v", "vibes").sounds)


def test_an_unknown_instrument_is_named():
    with pytest.raises(ValueError, match="'kazoo'"):
        sampled("x", "kazoo")
