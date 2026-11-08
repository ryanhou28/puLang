"""
The kaiDAW features the two songs asked for: time signatures, markers, the master
fader, controller lanes, and whole patches.
"""

from __future__ import annotations

import struct

import pytest

from pypulang import IV, I, Role, V, piece, root_quarters, vi
from pypulang.backends.kaidaw import SongState, push
from pypulang.backends.kaidaw import sync as sync_module
from pypulang.compiler import compile_piece
from pypulang.compiler.dialects import daw
from pypulang.compiler.passes.perform import Bend
from pypulang.dsl import device
from pypulang.pitches import A5, B5, D5, G5
from pypulang.sounds import surge_patches
from pypulang.sounds.surge import SURGE_XT, surge
from pypulang.sounds.surge_patches import (
    component_of,
    from_juce_base64,
    juce_base64,
    patch_from_fxp,
    vst3_state,
)


@pytest.fixture
def state(tmp_path) -> SongState:
    return SongState(tmp_path / "song.pulang")


def odd_meter_song(patch: str | None = None, bend: bool = False, master: float | None = None):
    with piece(tempo=120, key="G major", title="gaps") as p:
        verse = p.section("verse", bars=2)
        verse.harmony(I, vi)
        verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-2)
        verse.track("lead", role=Role.MELODY).notes([(B5, 1), (A5, 1 / 2), (G5, 1 / 2)])
        bridge = p.section("bridge", bars=2, time_sig="7/8")
        bridge.harmony(IV, V)
        # Two bars of 7/8 are seven beats: a whole note and a dotted half
        bridge.track("lead", role=Role.MELODY).notes([(D5, 1), (B5, 3 / 4)])
        p.form([verse, bridge, verse])
        if patch is not None:
            p.rack("lead", surge("synth", patch=patch))
        if master is not None:
            p.rack("master", device("glue", "compressor"), volume=master)
    passes = [Bend(track="lead", semitones=1, min_length="1")] if bend else []
    return compile_piece(p.to_ir(), event_passes=passes).daw


def project_of(module) -> daw.ProjectOp:
    return next(op for op in module.body.block.ops if isinstance(op, daw.ProjectOp))


class TestMetersAndMarkers:
    def test_a_seven_eight_section_reaches_the_meter_map(self, client, state):
        push(odd_meter_song(), client, state)
        meters = client.projection()["meterMap"]
        assert [(m["numerator"], m["denominator"]) for m in meters] == [(4, 4), (7, 8), (4, 4)]
        # Two 4/4 bars, then two 7/8 bars of 3360 ticks each (3.5 quarters)
        assert [m["at"] for m in meters] == [0, 7680, 7680 + 2 * 3360]

    def test_each_section_is_a_marker(self, client, state):
        push(odd_meter_song(), client, state)
        markers = client.projection()["markers"]
        assert [m["name"] for m in markers] == ["verse#1", "bridge#1", "verse#2"]

    def test_pushing_again_sends_no_map_or_markers(self, client, state):
        push(odd_meter_song(), client, state)
        report = push(odd_meter_song(), client, state)
        assert report.operations == 0


class TestMasterFader:
    def test_the_master_rack_sets_the_master_fader(self, client, state):
        push(odd_meter_song(master=0.6), client, state)
        assert client.projection()["master"]["volume"] == pytest.approx(0.6, abs=1e-3)


class TestBend:
    def test_scoops_become_a_pitch_bend_lane_in_each_clip(self):
        project = project_of(odd_meter_song(bend=True))
        lead = next(t for t in project.tracks() if t.track.data == "lead")
        lanes = {c.key.data: c.controllers() for c in lead.clips()}
        assert all(len(v) == 1 for v in lanes.values())
        points = lanes["verse#1/lead"][0].point_list()
        # Starts a semitone down (a quarter of the way, with a 2-semitone range)
        # and comes back to rest.
        assert points[0][1] == pytest.approx(0.25)
        assert points[-1][1] == pytest.approx(0.5)
        assert all(0 <= t < 7680 for t, _ in points)

    def test_bend_lanes_are_not_automation(self):
        project = project_of(odd_meter_song(bend=True))
        lead = next(t for t in project.tracks() if t.track.data == "lead")
        assert lead.automations() == []

    def test_a_bend_reaches_the_daw_and_is_not_resent(self, client, state):
        push(odd_meter_song(bend=True), client, state)
        clips = [c for c in client.projection("detail")["clips"] if c["name"].endswith("/lead")]
        assert clips and all("pitchbend" in c.get("controllers", {}) for c in clips)
        assert push(odd_meter_song(bend=True), client, state).operations == 0

    def test_an_unknown_kind_is_refused(self):
        with pytest.raises(ValueError, match="scoop"):
            compile_piece(_plain_piece(), event_passes=[Bend(track="lead", kind="wobble")])


def _plain_piece():
    with piece(tempo=120, key="C major", title="plain") as p:
        s = p.section("a", bars=1)
        s.harmony(I)
        s.track("lead", role=Role.MELODY).notes([(G5, 4)])
        p.form([s])
    return p.to_ir()


class TestPatches:
    def test_a_named_patch_is_restored_before_parameters(self, client, state, monkeypatch):
        if client.health().get("engine") != "fake":
            pytest.skip("the real engine needs a real Surge patch; see test_surge_real")
        monkeypatch.setattr(sync_module, "patch_state", lambda identifier, name: f"state:{name}")
        push(odd_meter_song(patch="Keys/Artificial 1"), client, state)
        plugins = client.projection()["plugins"]
        assert any(p.get("state") == "state:Keys/Artificial 1" for p in plugins)
        # Only when the source names a different patch
        assert push(odd_meter_song(patch="Keys/Artificial 1"), client, state).operations == 0
        push(odd_meter_song(patch="Leads/Acid"), client, state)
        assert any(p.get("state") == "state:Leads/Acid" for p in client.projection()["plugins"])

    def test_a_surge_device_from_a_patch_skips_the_init_defaults(self):
        assert surge("synth", patch="Keys/Artificial 1").params == {}
        assert surge("synth").params  # the defaults that make a sound from Init Saw


class TestSurgeState:
    def test_juce_base64_is_juces_format(self):
        assert juce_base64(b"") == "0."
        assert juce_base64(b"\x00") == "1..."
        # Low six bits first, from JUCE's own table
        assert juce_base64(b"\xff") == "1.+C"

    def test_juce_base64_round_trips(self):
        data = bytes(range(256)) * 3
        assert from_juce_base64(juce_base64(data)) == data

    def test_an_fxp_unwraps_to_its_patch(self):
        raw = b"sub3" + b"\x00" * 12 + b"<patch/>"
        header = (
            b"CcnK"
            + struct.pack(">I", 0)
            + b"FPCh"
            + struct.pack(">I", 1)
            + b"cjs3"
            + struct.pack(">II", 1, 1)
            + b"name".ljust(28, b"\0")
            + struct.pack(">I", len(raw))
        )
        assert patch_from_fxp(header + raw) == raw
        with pytest.raises(ValueError, match="another plugin"):
            patch_from_fxp(header.replace(b"cjs3", b"XfsX") + raw)

    def test_a_state_round_trips_through_the_vst3_envelope(self):
        raw = b"sub3 a patch"
        assert component_of(vst3_state(raw)) == raw

    def test_a_factory_patch_is_found_when_surge_is_installed(self):
        if not surge_patches.factory_dirs():
            pytest.skip("no Surge XT factory patches on this machine")
        assert component_of(surge_patches.patch_state("Keys/Artificial 1"))[:4] == b"sub3"

    def test_a_missing_patch_names_where_it_looked(self):
        with pytest.raises(FileNotFoundError, match="no Surge patch"):
            surge_patches.find_patch("Nowhere/Nothing")

    def test_only_surge_patches_are_read(self):
        with pytest.raises(sync_module.KaidawError, match="cannot read patches"):
            sync_module.patch_state("4osc", "anything")
        assert SURGE_XT.startswith("VST3-Surge XT")
