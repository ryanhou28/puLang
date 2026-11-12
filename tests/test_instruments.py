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


class TestLayers:
    def test_a_layered_instrument_has_a_sound_per_root_per_layer(self):
        device = sampled("keys", "piano")
        assert len(device.sounds) == 3 * 42 <= 128
        ranges = {(s["low_velocity"], s["high_velocity"]) for s in device.sounds}
        assert ranges == {(1, 64), (65, 100), (101, 127)}
        assert {s["file"].split("/")[-2] for s in device.sounds} == {"piano", "soft", "loud"}

    def test_layers_cover_every_velocity_once(self):
        for name, spec in INSTRUMENTS.items():
            ranges = sorted([spec.velocities, *(x.velocities for x in spec.layers)])
            assert ranges[0][0] == 1 and ranges[-1][1] == 127, name
            for (_, high), (low, _) in zip(ranges, ranges[1:], strict=False):
                assert low == high + 1, name

    def test_every_layer_zones_its_own_roots(self):
        for name, spec in INSTRUMENTS.items():
            for layer in spec.layers:
                roots = [root for root, _, _ in zones(name, layer.name)]
                assert roots == layer.roots(), name

    def test_without_layers_the_main_one_plays_at_every_velocity(self):
        device = sampled("keys", "piano", layers=False)
        assert len(device.sounds) == 42
        assert not any("low_velocity" in s for s in device.sounds)
        assert all(s["release"] == 250.0 for s in device.sounds)

    def test_one_shots_keep_no_release(self):
        assert not any("release" in s for s in sampled("v", "vibes").sounds)


class TestToKaidaw:
    def test_velocities_and_release_reach_the_sampler(self, tmp_path):
        from pypulang import Role, piece
        from pypulang.backends.kaidaw import KaidawClient, SongState, push
        from pypulang.compiler import compile_piece
        from tests.fake_kaidaw import FakeKaidaw
        from tests.test_song_audio import write_wav

        folder = tmp_path / "samples" / "instruments"
        spec = INSTRUMENTS["tenor_sax"]
        for sub, roots in [("", spec.roots()), ("loud/", spec.layers[0].roots())]:
            for root in roots:
                path = folder / "tenor_sax" / f"{sub}{root}.wav"
                path.parent.mkdir(parents=True, exist_ok=True)
                write_wav(path, 100 + root + (50 if sub else 0), 0.01)
        with piece(tempo=120, key="C major") as p:
            p.rack("sax", sampled("sax", "tenor_sax"))
            a = p.section("a", bars=1)
            a.track("sax", role=Role.MELODY).line("c4/1")
            p.form([a])
        client = KaidawClient(transport=FakeKaidaw())
        push(compile_piece(p.to_ir()).daw, client, SongState(tmp_path / "song.pulang"), fresh=True)
        sounds = next(x for x in client.projection()["plugins"] if x.get("sounds"))["sounds"]
        assert len(sounds) == 46
        assert {(s.get("lowVelocity"), s.get("highVelocity")) for s in sounds} == {
            (1, 90),
            (91, 127),
        }
        assert {s.get("releaseMs") for s in sounds} == {100.0}

    def test_a_sampler_without_them_sends_neither(self):
        from pypulang.backends.kaidaw.sync import _sound_specs
        from pypulang.compiler.dialects import daw

        device = daw.PluginOp(
            "kit",
            "sampler",
            {},
            None,
            [
                {
                    "file": "k.wav",
                    "root": 36,
                    "low": 36,
                    "high": 36,
                    "gain": 0.0,
                    "pan": 0.0,
                    "one_shot": True,
                }
            ],
        )
        (spec,) = _sound_specs(device, {"k.wav": {"id": "asset-1"}})
        assert "lowVelocity" not in spec and "releaseMs" not in spec
