"""
Surge XT through a real engine.

These need a server, because everything they pin down lives in the plugin: the fake
has no opinion about what happens to an oscillator's parameters when its type changes.
They do not delete tracks. Deleting a track holding Surge XT after a render has crashed
kaiDAW twice, so each test adds its own.
"""

from __future__ import annotations

import os
import shutil
import uuid

import pytest

from pypulang import Role, grid, piece
from pypulang.analysis import dominant_frequency, load, measure, pitch_track
from pypulang.backends.kaidaw import SongState, push
from pypulang.backends.kaidaw.client import KaidawClient, WslTransport
from pypulang.compiler import compile_piece
from pypulang.sounds.surge import SURGE_XT, electric_piano, kick, surge

pytestmark = pytest.mark.skipif(
    not os.environ.get("KAIDAW_TEST_PORT"),
    reason="set KAIDAW_TEST_PORT to run against a real server",
)


@pytest.fixture
def client() -> KaidawClient:
    return KaidawClient(transport=WslTransport(int(os.environ["KAIDAW_TEST_PORT"])))


def play(client, tmp_path, patch, pitch, gate=2, passes=lambda name: []):
    """Push one note on a new track, and render it alone."""
    name = f"t{uuid.uuid4().hex[:8]}"
    with piece(tempo=120) as p:
        p.rack(name, patch, volume=0.74)
        s = p.section("a", bars=1)
        s.track(name, role=Role.RHYTHM).pattern(
            grid(cell="x...............", pitch=pitch, gate=gate)
        )
    state = SongState(tmp_path / f"{name}.pulang")
    push(compile_piece(p.to_ir(), event_passes=passes(name)).daw, client, state, fresh=True)
    lock = state.load_lock()
    track = lock.tracks[name]["id"]
    projection = client.projection("summary")
    client.apply(
        [
            {"type": "SetTrackState", "trackId": t["id"], "muted": t["id"] != track}
            for t in projection["tracks"]
        ],
        projection["revision"],
        "solo for test",
    )
    wav = f"pulang-test-{name}.wav"
    transport = client.transport
    client.render(f"{transport.share_win}\\{wav}", 0.0, 1.0)
    target = tmp_path / wav
    shutil.move(str(transport.share_wsl / wav), target)
    plugin = next(
        x
        for x in client.projection("detail")["plugins"]
        if x["id"] == lock.devices[f"{name}/synth"]["id"]
    )
    return load(str(target)), plugin, lock.schemas[SURGE_XT]


def test_oscillator_parameters_survive_a_type_change(client, tmp_path):
    (samples, rate), plugin, ids = play(client, tmp_path, surge("synth", electric_piano()), 60)
    display = plugin["parameterDisplay"]
    # Parameter ids are the stable handle. Surge renames a parameter to suit the active
    # oscillator on its first instance in a process ("Sub Mix" becomes "M2 Ratio").
    #
    # Display strings only read like this once FM2 is really the active oscillator,
    # and they would be its defaults if the write had been wiped.
    assert display[ids["A Osc 1 Sub Mix"]] == "C : 14"
    assert display[ids["A Osc 1 Shape"]] == "20.00 %"
    assert measure(samples, rate).rms_db > -60


def test_the_kick_sweeps_down_to_its_resting_pitch(client, tmp_path):
    (samples, rate), _, _ = play(client, tmp_path, surge("synth", kick()), 31)
    track = pitch_track(samples[: int(0.2 * rate)], rate, 6)
    assert max(track[:4]) > 150
    assert 40 < dominant_frequency(samples[int(0.05 * rate) : int(0.15 * rate)], rate) < 70


def test_identifier_is_the_one_installed(client):
    assert SURGE_XT in {
        p["identifier"] if "identifier" in p else p.get("id") for p in client.plugins()
    }


def test_a_factory_patch_loads_whole(client, tmp_path):
    from pypulang.sounds import surge_patches
    from pypulang.sounds.surge_patches import component_of

    if not surge_patches.factory_dirs():
        pytest.skip("no Surge XT factory patches on this machine")
    (samples, rate), plugin, _ = play(
        client, tmp_path, surge("synth", patch="Keys/Soft Suitcase"), 60
    )
    # The patch's own name, read back out of the plugin's state: the factory file
    # reached Surge whole, through RestorePluginState, and made a sound.
    assert b'<meta name="Softsuit"' in component_of(client.plugin_state(plugin["id"]))
    assert measure(samples, rate).rms_db > -60


def test_a_pitch_bend_lane_bends_the_note(client, tmp_path):
    """A two-semitone scoop over a beat: a G at the start of an A, then the A."""
    from pypulang.compiler.passes.perform import Bend

    (samples, rate), _, _ = play(
        client,
        tmp_path,
        surge("synth"),
        69,
        gate=16,
        passes=lambda name: [Bend(track=name, kind="scoop", semitones=2, time="1", min_length="1")],
    )
    start = dominant_frequency(samples[: int(0.06 * rate)], rate)
    settled = dominant_frequency(samples[int(0.6 * rate) : int(0.9 * rate)], rate)
    assert 380 < start < 405  # 392 Hz, two semitones under 440
    assert 435 < settled < 445
