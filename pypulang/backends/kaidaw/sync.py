"""
Keeping a song and a kaiDAW project in step.

The rule that decides everything here is ownership:

    The source owns generated notes, sections and tempo.
    The DAW owns plugin state, the mix, automation it drew, and any clip made by hand.

A plugin parameter or fader the source declares is only written when the source
value changes, so a knob turned in the DAW stays turned until the source says
otherwise.

`push` runs: capture DAW edits, apply overrides to the compiled project, diff, and
send one transaction. Undoing that transaction in the DAW undoes the recompile.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xdsl.dialects.builtin import IntegerAttr, ModuleOp, i64

from pypulang.backends.kaidaw.client import KaidawClient, KaidawError
from pypulang.backends.kaidaw.state import Lock, Overrides, SongState
from pypulang.compiler.dialects import daw
from pypulang.compiler.dialects.mus import from_attr
from pypulang.compiler.locs import loc_key, name_loc

# kaiDAW's master bus is addressed by this name. It holds a plugin chain and, since
# kaiDAW's song-gaps work, a fader: volume and pan, but no name or colour.
MASTER = "master"


@dataclass
class SyncReport:
    """What a sync did, in terms a person can check."""

    operations: int = 0
    tracks_created: int = 0
    clips_created: int = 0
    clips_deleted: int = 0
    notes_added: int = 0
    notes_updated: int = 0
    notes_deleted: int = 0
    notes_unchanged: int = 0
    captured: int = 0
    stale: list[str] = field(default_factory=list)
    orphaned: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    revision: int | None = None

    def summary(self) -> str:
        lines = [
            f"{self.operations} operations: "
            f"{self.notes_added} notes added, {self.notes_updated} updated, "
            f"{self.notes_deleted} deleted, {self.notes_unchanged} unchanged; "
            f"{self.tracks_created} tracks, {self.clips_created} clips created, "
            f"{self.clips_deleted} clips deleted"
        ]
        if self.captured:
            lines.append(f"Kept {self.captured} edit(s) made in the DAW")
        lines.extend(f"Stale edit: {s}" for s in self.stale)
        lines.extend(f"Orphaned edit: {s}" for s in self.orphaned)
        lines.extend(self.warnings)
        return "\n".join(lines)


def _project(module: ModuleOp) -> daw.ProjectOp:
    for op in module.body.block.ops:
        if isinstance(op, daw.ProjectOp):
            return op
    raise ValueError("Expected a daw.project")


def _note_of(wire: dict[str, Any]) -> list[int]:
    return [wire["pitch"], wire["start"], wire["duration"], wire["velocity"]]


def _wire_note(note: list[int] | tuple[int, ...], note_id: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "pitch": note[0],
        "start": note[1],
        "duration": note[2],
        "velocity": note[3],
    }
    if note_id is not None:
        result["id"] = note_id
    return result


class DawState:
    """A detail projection, indexed."""

    def __init__(self, projection: dict[str, Any]):
        self.revision: int = projection["revision"]
        self.tempo_map: list[dict[str, Any]] = projection.get("tempoMap", [])
        self.meter_map: list[dict[str, Any]] = projection.get(
            "meterMap", [{"at": 0, "numerator": 4, "denominator": 4}]
        )
        self.markers: list[dict[str, Any]] = projection.get("markers", [])
        self.tracks = {t["id"]: t for t in projection["tracks"]}
        if "master" in projection:
            self.tracks[MASTER] = projection["master"]
        self.clips = {c["id"]: c for c in projection["clips"]}
        self.plugins = {p["id"]: p for p in projection["plugins"]}

    def notes(self, clip_id: str) -> dict[str, list[int]]:
        return {n["id"]: _note_of(n) for n in self.clips[clip_id].get("notes", [])}

    def track_plugin(self, track_id: str, name_prefix: str) -> str | None:
        for plugin_id in self.tracks[track_id]["pluginIds"]:
            if self.plugins[plugin_id]["name"].startswith(name_prefix):
                return plugin_id
        return None


# -----------------------------------------------------------------------------
# Capture: what changed in the DAW since the last push
# -----------------------------------------------------------------------------


def capture(lock: Lock, overrides: Overrides, state: DawState) -> int:
    """
    Record every hand edit since the last push in `overrides`.

    A note missing from its clip was deleted by a person, and that is an edit like
    any other. Treating it as "nothing to preserve" brings the note back on the next
    push, because kaiDAW creates a note when it is sent an id it does not know.

    Returns:
        How many edits this call recorded
    """
    captured = 0
    track_names = {info["id"]: name for name, info in lock.tracks.items()}

    for clip_key, info in lock.clips.items():
        live = state.clips.get(info["id"])
        if live is None:
            if not overrides.clips.get(clip_key, {}).get("deleted"):
                overrides.clips[clip_key] = {"deleted": True}
                captured += 1
            continue

        moved = overrides.clips.setdefault(clip_key, {})
        for field_name, wire_name in (("start", "start"), ("length", "length")):
            if live[wire_name] != info[field_name]:
                if moved.get(field_name) != live[wire_name]:
                    captured += 1
                moved[field_name] = live[wire_name]
        if live["trackId"] != lock.tracks[info["track"]]["id"]:
            name = track_names.get(live["trackId"])
            if name is not None and moved.get("track") != name:
                moved["track"] = name
                captured += 1
        if not moved:
            del overrides.clips[clip_key]

        live_notes = state.notes(info["id"])
        drawn = {item["key"]: item for item in overrides.added.get(clip_key, [])}
        known = set()
        for loc, entry in lock.notes_in(clip_key).items():
            known.add(entry["id"])
            now = live_notes.get(entry["id"])
            if now == entry["note"]:
                continue
            captured += 1
            if loc in drawn:
                # A note drawn by hand has no source to fall back on: it simply follows
                # the DAW, and deleting it deletes it.
                if now is None:
                    overrides.added[clip_key].remove(drawn[loc])
                else:
                    drawn[loc]["note"] = now
            else:
                existing = overrides.notes.get(loc)
                base = existing["base"] if existing else entry["note"]
                if now is None:
                    if existing and existing.get("deleted"):
                        captured -= 1
                    else:
                        overrides.notes[loc] = {"deleted": True, "base": base}
                elif now == base:
                    overrides.notes.pop(loc, None)
                else:
                    overrides.notes[loc] = {"note": now, "base": base}
            if now is not None:
                entry["note"] = now

        for note_id, note in live_notes.items():
            if note_id not in known:
                key = f"{clip_key}/added/{note[1]}:{note[0]}:{note_id}"
                overrides.added.setdefault(clip_key, []).append({"key": key, "note": note})
                lock.notes[key] = {"clip": clip_key, "id": note_id, "note": note}
                captured += 1
    return captured


# -----------------------------------------------------------------------------
# Overrides: the compile step that keeps hand edits
# -----------------------------------------------------------------------------


def _track_ops(project: daw.ProjectOp) -> dict[str, daw.TrackOp]:
    return {t.track.data: t for t in project.tracks()}


def apply_overrides(module: ModuleOp, overrides: Overrides, report: SyncReport) -> None:
    """
    Rewrite a compiled project so it includes every edit made in the DAW.

    An edit whose note the source no longer makes is kept as a plain note and
    reported, because silently dropping work is the one thing this must not do.
    """
    project = _project(module)
    tracks = _track_ops(project)
    seen: set[str] = set()

    for track in project.tracks():
        # Audio clips are moved, resized and deleted by hand like any clip; they
        # have no notes, so the clip directives are all there is to apply.
        for audio in track.audio_clips():
            directive = overrides.clips.get(audio.key.data, {})
            if directive.get("deleted"):
                track.body.block.detach_op(audio)
                continue
            if "start" in directive:
                audio.properties["start"] = IntegerAttr(directive["start"], i64)
            if "length" in directive:
                audio.properties["length"] = IntegerAttr(directive["length"], i64)
            if "track" in directive and directive["track"] in tracks:
                track.body.block.detach_op(audio)
                tracks[directive["track"]].body.block.add_op(audio)
        for clip in track.clips():
            key = clip.key.data
            directive = overrides.clips.get(key, {})
            if directive.get("deleted"):
                track.body.block.detach_op(clip)
                seen.update(loc_key(n.location) for n in clip.notes())
                continue
            if "start" in directive:
                clip.properties["start"] = IntegerAttr(directive["start"], i64)
            if "length" in directive:
                clip.properties["length"] = IntegerAttr(directive["length"], i64)
            if "track" in directive and directive["track"] in tracks:
                track.body.block.detach_op(clip)
                tracks[directive["track"]].body.block.add_op(clip)

            for note in clip.notes():
                loc = loc_key(note.location)
                entry = overrides.notes.get(loc)
                if entry is None:
                    continue
                seen.add(loc)
                lowered = list(note.as_tuple())
                if lowered != entry["base"]:
                    report.stale.append(
                        f"{loc}: edited when the source gave {entry['base']}, "
                        f"source now gives {lowered}"
                    )
                if entry.get("deleted"):
                    clip.body.block.detach_op(note)
                else:
                    replacement = daw.NoteOp(*entry["note"])
                    replacement.location = note.location
                    clip.body.block.insert_op_before(replacement, note)
                    clip.body.block.detach_op(note)

    clips = {c.key.data: c for t in project.tracks() for c in t.clips()}
    for loc, entry in overrides.notes.items():
        if loc in seen:
            continue
        report.orphaned.append(
            f"{loc}: the source no longer makes this note"
            + ("" if entry.get("deleted") else "; keeping the edited note")
        )
        clip_key = "/".join(loc.split("/")[:2])
        if not entry.get("deleted") and clip_key in clips:
            kept = daw.NoteOp(*entry["note"])
            kept.location = name_loc(loc)
            clips[clip_key].body.block.add_op(kept)

    for clip_key, added in overrides.added.items():
        if clip_key in clips:
            for item in added:
                note = daw.NoteOp(*item["note"])
                note.location = name_loc(item["key"])
                clips[clip_key].body.block.add_op(note)


# -----------------------------------------------------------------------------
# Plan: the difference between the project we want and the one that exists
# -----------------------------------------------------------------------------


def _schema(lock: Lock, state: DawState, identifier: str, plugin_id: str) -> dict[str, str]:
    """Published parameter name to parameter id, cached per plugin type."""
    if identifier not in lock.schemas and plugin_id in state.plugins:
        plugin = state.plugins[plugin_id]
        lock.schemas[identifier] = dict(
            zip(plugin["parameterNames"], plugin["parameters"], strict=True)
        )
    return lock.schemas.get(identifier, {})


def _plan_structure(
    project: daw.ProjectOp,
    lock: Lock,
    state: DawState,
    report: SyncReport,
    assets: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Tempo, tracks, devices, clips and notes: everything that needs no plugin schema."""
    ops: list[dict[str, Any]] = []

    # Tempo and time signatures are one map in kaiDAW, sent whole when either moves.
    current_tempo = [{"at": p["at"], "bpm": p["bpm"]} for p in state.tempo_map]
    wanted_tempo = [
        {"at": t.at.value.data, "bpm": t.bpm.value.data} for t in project.tempos()
    ] or current_tempo
    current_meters = [
        {"at": m["at"], "numerator": m["numerator"], "denominator": m["denominator"]}
        for m in state.meter_map
    ]
    wanted_meters = [
        {
            "at": m.at.value.data,
            "numerator": m.numerator.value.data,
            "denominator": m.denominator.value.data,
        }
        for m in project.meters()
    ] or current_meters
    if wanted_tempo != current_tempo or wanted_meters != current_meters:
        ops.append({"type": "SetTempoMap", "points": wanted_tempo, "meters": wanted_meters})

    # Sections are the source's, so their markers are too: sent whole when they differ.
    wanted_markers = [{"at": m.at.value.data, "name": m.label.data} for m in project.markers()]
    current_markers = [{"at": m["at"], "name": m["name"]} for m in state.markers]
    if project.markers() and wanted_markers != current_markers:
        ops.append({"type": "SetMarkers", "markers": wanted_markers})

    wanted_clips: set[str] = set()
    for track in project.tracks():
        name = track.track.data
        info = lock.tracks.get(name)
        devices = track.plugins()
        if name == MASTER:
            track_ref = MASTER
        elif info is None or info["id"] not in state.tracks:
            track_ref = f"$track_{len(ops)}"
            ops.append(
                {
                    "type": "CreateTrack",
                    "alias": track_ref,
                    "name": name,
                    "withInstrument": not devices,
                }
            )
            report.tracks_created += 1
        else:
            track_ref = info["id"]

        ops.extend(_plan_mix(track, track_ref, info))
        ops.extend(_plan_devices(track, track_ref, lock))

        for clip in track.clips():
            wanted_clips.add(clip.key.data)
            ops.extend(_plan_clip(clip, track_ref, lock, state, report))
        for audio in track.audio_clips():
            wanted_clips.add(audio.key.data)
            ops.extend(_plan_audio(audio, track_ref, lock, state, report, assets or {}))

    for clip_key, info in lock.clips.items():
        if clip_key not in wanted_clips and info["id"] in state.clips:
            ops.append({"type": "DeleteClip", "clipId": info["id"]})
            report.clips_deleted += 1
    return ops


def _audio_record(audio: daw.AudioClipOp, asset: str) -> dict[str, Any]:
    return {
        "asset": asset,
        "start": audio.start.value.data,
        "length": audio.length.value.data if audio.length is not None else None,
        "offset": audio.offset.value.data,
        "gain": audio.gain.value.data,
    }


def _plan_audio(
    audio: daw.AudioClipOp,
    track_ref: str,
    lock: Lock,
    state: DawState,
    report: SyncReport,
    assets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    An audio clip, created or brought in line with the source.

    Compared with the last push, as notes and parameters are: a clip moved in the
    DAW is captured as an override and is already in `audio` by the time this runs.
    A different file or offset is a different clip, so it is replaced.
    """
    key = audio.key.data
    asset = assets.get(audio.file.data, {}).get("id")
    if asset is None:
        report.warnings.append(f"{key}: no audio for {audio.file.data}")
        return []
    wanted = _audio_record(audio, asset)
    info = lock.clips.get(key)
    live = info is not None and info["id"] in state.clips
    create = {
        "type": "CreateAudioClip",
        "alias": "$audio_" + key.replace("#", "_").replace("/", "_").replace(" ", "_"),
        "trackId": track_ref,
        "assetId": asset,
        "name": key,
        "start": wanted["start"],
        "offsetSeconds": wanted["offset"],
        "gainDb": wanted["gain"],
    }
    if wanted["length"] is not None:
        create["length"] = wanted["length"]
    if not live:
        report.clips_created += 1
        return [create]
    before = info.get("audio", {})
    clip_id = info["id"]
    if before.get("asset") != asset or before.get("offset") != wanted["offset"]:
        report.clips_created += 1
        report.clips_deleted += 1
        return [{"type": "DeleteClip", "clipId": clip_id}, create]
    ops: list[dict[str, Any]] = []
    if before.get("start") != wanted["start"]:
        ops.append({"type": "MoveClip", "clipId": clip_id, "start": wanted["start"]})
    if wanted["length"] is not None and before.get("length") != wanted["length"]:
        ops.append({"type": "ResizeClip", "clipId": clip_id, "length": wanted["length"]})
    if before.get("gain") != wanted["gain"]:
        ops.append({"type": "SetClipState", "clipId": clip_id, "gainDb": wanted["gain"]})
    return ops


def import_assets(
    project: daw.ProjectOp, client: KaidawClient, lock: Lock, base: Path
) -> dict[str, dict[str, Any]]:
    """
    Every audio file the project uses, in kaiDAW's pool.

    Files are named relative to the song. One already imported is not sent again
    unless it changed on disk or the server has lost it (a fresh server, say).

    Returns:
        File as the song names it, to the asset
    """
    files = {a.file.data for t in project.tracks() for a in t.audio_clips()}
    files |= {str(s["file"]) for t in project.tracks() for d in t.plugins() for s in d.sound_list()}
    if not files:
        return {}
    pool = {a["id"] for a in client.assets()}
    result: dict[str, dict[str, Any]] = {}
    for name in sorted(files):
        path = (base / name).resolve()
        if not path.is_file():
            raise KaidawError(f"no audio file {name} (looked at {path})")
        stat = path.stat()
        known = lock.assets.get(str(path))
        if (
            known
            and known["size"] == stat.st_size
            and known["mtime"] == stat.st_mtime
            and known["id"] in pool
        ):
            result[name] = known
            continue
        asset = client.import_asset(path)
        entry = {
            "id": asset["id"],
            "seconds": asset["seconds"],
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        }
        lock.assets[str(path)] = entry
        result[name] = entry
    return result


def _plan_mix(
    track: daw.TrackOp, track_ref: str, info: dict[str, Any] | None
) -> list[dict[str, Any]]:
    change: dict[str, Any] = {}
    last = info or {}
    if track.volume is not None and last.get("volume") != track.volume.value.data:
        change["volume"] = track.volume.value.data
    if track.pan is not None and last.get("pan") != track.pan.value.data:
        change["pan"] = track.pan.value.data
    if (
        track.color is not None
        and last.get("color") != track.color.data
        and track.track.data != MASTER  # the master has no colour to set
    ):
        change["color"] = track.color.data
    if not change:
        return []
    return [{"type": "SetTrackState", "trackId": track_ref, **change}]


def _plan_devices(track: daw.TrackOp, track_ref: str, lock: Lock) -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = []
    for index, device in enumerate(track.plugins()):
        key = f"{track.track.data}/{device.device.data}"
        known = lock.devices.get(key)
        if known is not None and known["identifier"] == device.identifier.data:
            continue
        if known is not None:
            ops.append({"type": "RemovePlugin", "pluginId": known["id"]})
        alias = f"$dev_{track.track.data}_{index}".replace(" ", "_")
        ops.append(
            {
                "type": "AddPlugin",
                "alias": alias,
                "trackId": track_ref,
                "identifier": device.identifier.data,
            }
        )
        # kaiDAW inserts a plugin just before the fader, so devices added in order
        # land in order. A device replaced in the middle of a chain still lands at
        # the end of the devices, which is what this puts right.
        ops.append({"type": "MovePlugin", "pluginId": alias, "index": index})
    return ops


def _plan_clip(
    clip: daw.ClipOp, track_ref: str, lock: Lock, state: DawState, report: SyncReport
) -> list[dict[str, Any]]:
    key = clip.key.data
    info = lock.clips.get(key)
    wanted = {loc_key(n.location): list(n.as_tuple()) for n in clip.notes()}

    if info is None or info["id"] not in state.clips:
        report.clips_created += 1
        report.notes_added += len(wanted)
        alias = f"$clip_{key}".replace("#", "_").replace("/", "_").replace(" ", "_")
        return [
            {
                "type": "CreateClip",
                "alias": alias,
                "trackId": track_ref,
                "name": key,
                "start": clip.start.value.data,
                "length": clip.length.value.data,
                "notes": [_wire_note(n) for n in wanted.values()],
            },
            *_plan_controllers(clip, alias, {}),
        ]

    ops: list[dict[str, Any]] = []
    clip_id = info["id"]
    live = state.clips[clip_id]
    if live["start"] != clip.start.value.data:
        ops.append({"type": "MoveClip", "clipId": clip_id, "start": clip.start.value.data})
    if live["length"] != clip.length.value.data:
        ops.append({"type": "ResizeClip", "clipId": clip_id, "length": clip.length.value.data})

    live_notes = state.notes(clip_id)
    known = lock.notes_in(key)
    upserts: list[dict[str, Any]] = []
    for loc, note in wanted.items():
        entry = known.get(loc)
        note_id = entry["id"] if entry else None
        current = live_notes.get(note_id) if note_id else None
        if current == note:
            report.notes_unchanged += 1
        elif current is None:
            upserts.append(_wire_note(note))
            report.notes_added += 1
        else:
            upserts.append(_wire_note(note, note_id))
            report.notes_updated += 1
    deletions = [
        entry["id"]
        for loc, entry in known.items()
        if loc not in wanted and entry["id"] in live_notes
    ]
    report.notes_deleted += len(deletions)
    if upserts:
        ops.append({"type": "UpsertNotes", "clipId": clip_id, "notes": upserts})
    if deletions:
        ops.append({"type": "DeleteNotes", "clipId": clip_id, "noteIds": deletions})
    ops.extend(_plan_controllers(clip, clip_id, lock.controllers))
    return ops


def _plan_controllers(
    clip: daw.ClipOp, clip_ref: str, pushed: dict[str, list[list[float]]]
) -> list[dict[str, Any]]:
    """
    Controller lanes whose source changed since the last push.

    Compared with what was pushed, not with the DAW, for the reason parameters are:
    a bend redrawn in the DAW stays redrawn until the source says otherwise. A lane
    the source stops making is left alone too, as a hand-drawn one would be.
    """
    ops = []
    for lane in clip.controllers():
        points = [[t, v] for t, v in lane.point_list()]
        if pushed.get(f"{clip.key.data}/{lane.controller.data}") == points:
            continue
        ops.append(
            {
                "type": "SetControllerPoints",
                "clipId": clip_ref,
                "controller": lane.controller.data,
                "points": [{"at": t, "value": v} for t, v in points],
            }
        )
    return ops


def _is_selector(name: str) -> bool:
    """
    True for a parameter that chooses what other parameters mean.

    Setting Surge XT's "A Osc 1 Type" resets that oscillator's other parameters, and
    it does so on the next audio block rather than at once. See `_flush`.
    """
    return name.endswith(" Type")


def patch_state(identifier: str, patch: str) -> str:
    """
    A named patch as plugin state, for the plugins puLang knows how to read.

    Raises:
        KaidawError: For a plugin with no patch reader, or a patch not found
    """
    from pypulang.sounds.surge import SURGE_XT
    from pypulang.sounds.surge_patches import patch_state as surge_patch_state

    if identifier != SURGE_XT:
        raise KaidawError(f"puLang cannot read patches for {identifier!r}")
    try:
        return surge_patch_state(patch)
    except (FileNotFoundError, ValueError) as error:
        raise KaidawError(str(error)) from error


def _plan_patches(project: daw.ProjectOp, lock: Lock) -> list[dict[str, Any]]:
    """
    Whole-patch loads, for devices whose source names a different patch than last push.

    A patch replaces every parameter, so a device whose patch changes has the
    parameters its source declares written again on top, even unchanged ones.
    """
    ops: list[dict[str, Any]] = []
    for track in project.tracks():
        for device in track.plugins():
            if device.patch is None:
                continue
            entry = lock.devices[f"{track.track.data}/{device.device.data}"]
            if entry.get("patch") == device.patch.data:
                continue
            ops.append(
                {
                    "type": "RestorePluginState",
                    "pluginId": entry["id"],
                    "state": patch_state(entry["identifier"], device.patch.data),
                }
            )
            entry["params"] = {}
    return ops


def _plan_parameters(
    project: daw.ProjectOp, lock: Lock, state: DawState, report: SyncReport
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Parameters, automation and sends: these need ids that exist only after structure.

    Returns:
        Selector parameters, which must land first, and everything else
    """
    selectors: list[dict[str, Any]] = []
    ops: list[dict[str, Any]] = []
    for track in project.tracks():
        track_name = track.track.data
        track_id = lock.tracks[track_name]["id"]
        for device in track.plugins():
            key = f"{track_name}/{device.device.data}"
            entry = lock.devices[key]
            schema = _schema(lock, state, entry["identifier"], entry["id"])
            for name, value in _params(device).items():
                if entry["params"].get(name) == value:
                    continue
                if name not in schema:
                    report.warnings.append(f"{key}: no parameter named {name!r}")
                    continue
                (selectors if _is_selector(name) else ops).append(
                    {
                        "type": "SetPluginParameter",
                        "pluginId": entry["id"],
                        "parameterId": schema[name],
                        "value": value,
                    }
                )

        for automation in track.automations():
            target = f"{track_name}/{automation.device.data}/{automation.param.data}"
            points = [[t, v] for t, v in automation.point_list()]
            if lock.automations.get(target) == points:
                continue
            resolved = _resolve_target(track_id, automation, lock, state, track_name)
            if resolved is None:
                report.warnings.append(f"{target}: nothing to automate")
                continue
            ops.append(
                {
                    "type": "SetAutomationPoints",
                    "pluginId": resolved[0],
                    "parameterId": resolved[1],
                    "points": [{"at": t, "value": v} for t, v in points],
                }
            )

        for send in track.sends():
            key = f"{track_name}>{send.destination.data}"
            if key in lock.sends:
                continue
            ops.append(
                {
                    "type": "CreateSend",
                    "fromTrackId": track_id,
                    "toTrackId": lock.tracks[send.destination.data]["id"],
                    "gain": send.gain.value.data,
                }
            )
    return selectors, ops


def _sound_specs(device: daw.PluginOp, assets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "assetId": assets[str(s["file"])]["id"],
            "rootNote": int(s["root"]),
            "lowNote": int(s["low"]),
            "highNote": int(s["high"]),
            "gainDb": float(s["gain"]),
            "pan": float(s["pan"]),
            "openEnded": bool(s["one_shot"]),
        }
        for s in device.sound_list()
    ]


def _plan_sounds(
    project: daw.ProjectOp, lock: Lock, assets: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """A sampler's sounds, sent whole when the source's list changes."""
    ops = []
    for track in project.tracks():
        for device in track.plugins():
            if not device.sound_list():
                continue
            entry = lock.devices[f"{track.track.data}/{device.device.data}"]
            sounds = _sound_specs(device, assets)
            if entry.get("sounds") != sounds:
                ops.append({"type": "SetSamplerSounds", "pluginId": entry["id"], "sounds": sounds})
                entry["sounds"] = sounds
    return ops


def _params(device: daw.PluginOp) -> dict[str, float]:
    return {k: float(v) for k, v in from_attr(device.params).items()}


def _resolve_target(
    track_id: str,
    automation: daw.AutomationOp,
    lock: Lock,
    state: DawState,
    track_name: str,
) -> tuple[str, str] | None:
    """The plugin and parameter id an automation curve lands on."""
    device = automation.device.data
    param = automation.param.data
    if device == "mix":
        plugin_id = state.track_plugin(track_id, "Volume & Pan")
        return (plugin_id, param) if plugin_id else None
    entry = lock.devices.get(f"{track_name}/{device}")
    if entry is None:
        return None
    schema = _schema(lock, state, entry["identifier"], entry["id"])
    return (entry["id"], schema[param]) if param in schema else None


# -----------------------------------------------------------------------------
# Recording what the DAW now holds
# -----------------------------------------------------------------------------


def _record(project: daw.ProjectOp, lock: Lock, state: DawState, aliases: dict[str, str]) -> None:
    """Update the lock from a fresh projection, once the transaction has landed."""
    by_name = {t["name"]: t["id"] for t in state.tracks.values()}
    by_clip_name: dict[str, str] = {}
    for clip_id, clip in state.clips.items():
        by_clip_name.setdefault(clip["name"], clip_id)

    new_notes: dict[str, dict[str, Any]] = {}
    new_clips: dict[str, dict[str, Any]] = {}
    for track in project.tracks():
        name = track.track.data
        previous = lock.tracks.get(name, {})
        if name == MASTER:
            track_id = MASTER
        elif previous.get("id") in state.tracks:
            track_id = previous["id"]
        else:
            track_id = by_name[name]
        lock.tracks[name] = {
            "id": track_id,
            "volume": track.volume.value.data
            if track.volume is not None
            else previous.get("volume"),
            "pan": track.pan.value.data if track.pan is not None else previous.get("pan"),
            "color": track.color.data if track.color is not None else previous.get("color"),
        }
        for index, device in enumerate(track.plugins()):
            key = f"{name}/{device.device.data}"
            alias = f"$dev_{name}_{index}".replace(" ", "_")
            if alias in aliases:
                lock.devices[key] = {
                    "id": aliases[alias],
                    "identifier": device.identifier.data,
                    "params": {},
                }

        for clip in track.clips():
            key = clip.key.data
            previous_clip = lock.clips.get(key)
            if previous_clip is not None and previous_clip["id"] in state.clips:
                clip_id = previous_clip["id"]
            else:
                clip_id = by_clip_name[key]
            new_clips[key] = {
                "id": clip_id,
                "track": name,
                "start": clip.start.value.data,
                "length": clip.length.value.data,
            }
            _record_notes(clip, key, clip_id, lock, state, new_notes)
            for lane in clip.controllers():
                lock.controllers[f"{key}/{lane.controller.data}"] = [
                    [t, v] for t, v in lane.point_list()
                ]
        for audio in track.audio_clips():
            key = audio.key.data
            previous_clip = lock.clips.get(key)
            if previous_clip is not None and previous_clip["id"] in state.clips:
                clip_id = previous_clip["id"]
            else:
                clip_id = by_clip_name[key]
            live = state.clips[clip_id]
            new_clips[key] = {
                "id": clip_id,
                "track": name,
                "start": live["start"],
                "length": live["length"],
                "audio": _audio_record(audio, live.get("assetId", "")),
            }
    lock.clips = new_clips
    lock.notes = new_notes


def _record_notes(
    clip: daw.ClipOp,
    key: str,
    clip_id: str,
    lock: Lock,
    state: DawState,
    into: dict[str, dict[str, Any]],
) -> None:
    live = state.notes(clip_id)
    claimed: set[str] = set()
    pending: list[tuple[str, list[int]]] = []
    for note in clip.notes():
        loc = loc_key(note.location)
        wanted = list(note.as_tuple())
        previous = lock.notes.get(loc)
        if previous is not None and previous["id"] in live and live[previous["id"]] == wanted:
            into[loc] = {"clip": key, "id": previous["id"], "note": wanted}
            claimed.add(previous["id"])
        else:
            pending.append((loc, wanted))

    # Notes created by this push have ids we were not told. They are matched on
    # content, which is exact because we wrote that content a moment ago.
    unclaimed: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for note_id, note in live.items():
        if note_id not in claimed:
            unclaimed[tuple(note)].append(note_id)
    for loc, wanted in pending:
        ids = unclaimed.get(tuple(wanted))
        if not ids:
            raise KaidawError(f"{loc}: {wanted} did not arrive in clip {clip_id}")
        into[loc] = {"clip": key, "id": ids.pop(), "note": wanted}


def _record_parameters(project: daw.ProjectOp, lock: Lock) -> None:
    for track in project.tracks():
        name = track.track.data
        for device in track.plugins():
            entry = lock.devices[f"{name}/{device.device.data}"]
            entry["params"].update(_params(device))
            if device.patch is not None:
                entry["patch"] = device.patch.data
        for automation in track.automations():
            target = f"{name}/{automation.device.data}/{automation.param.data}"
            lock.automations[target] = [[t, v] for t, v in automation.point_list()]
        for send in track.sends():
            lock.sends[f"{name}>{send.destination.data}"] = send.gain.value.data


# -----------------------------------------------------------------------------
# The commands
# -----------------------------------------------------------------------------


def _check_lock(lock: Lock, state: DawState) -> None:
    if lock.empty:
        return
    ids = {info["id"] for info in lock.tracks.values()} - {MASTER}
    if ids and not ids & set(state.tracks):
        raise KaidawError(
            "None of this song's tracks exist in the open project. Open the project it "
            "was pushed to, or push with fresh=True to build it again here."
        )


def pull(client: KaidawClient, song: SongState) -> SyncReport:
    """Record edits made in the DAW into the song's overrides."""
    lock = song.load_lock()
    overrides = song.load_overrides()
    state = DawState(client.projection())
    _check_lock(lock, state)
    report = SyncReport(revision=state.revision)
    report.captured = capture(lock, overrides, state)
    song.save_overrides(overrides)
    song.save_lock(lock)
    return report


def status(module: ModuleOp, client: KaidawClient, song: SongState) -> SyncReport:
    """What a push would do, without writing anything to the DAW or the song."""
    return push(module, client, song, dry_run=True)


def push(
    module: ModuleOp,
    client: KaidawClient,
    song: SongState,
    fresh: bool = False,
    dry_run: bool = False,
) -> SyncReport:
    """
    Make the DAW hold this compiled project, keeping edits made there.

    Args:
        module: A `daw` module. It is rewritten in place by the song's overrides.
        client: The server
        song: Where the lock and overrides live
        fresh: Ignore the lock and build the project from nothing. Overrides still
            apply, because they belong to the song and not to one project.
        dry_run: Work out what would change and report it, changing nothing

    Raises:
        KaidawError: If the server refused. The transaction is atomic, so a refusal
            leaves the project as it was.
    """
    lock = Lock() if fresh else song.load_lock()
    overrides = song.load_overrides()
    state = DawState(client.projection())
    _check_lock(lock, state)

    report = SyncReport()
    report.captured = capture(lock, overrides, state)
    apply_overrides(module, overrides, report)
    project = _project(module)

    if dry_run:
        report.operations = len(_plan_structure(project, lock, state, report, {}))
        return report
    assets = import_assets(project, client, lock, song.directory.parent)
    structure = _plan_structure(project, lock, state, report, assets)
    report.operations = len(structure)

    aliases: dict[str, str] = {}
    revision = state.revision
    if structure:
        result = client.apply(structure, revision, "pulang push")
        aliases = result.get("aliases", {})
        revision = result["revision"]
        state = DawState(client.projection())
    _record(project, lock, state, aliases)

    # Patches first and alone: Surge XT loads a state on its next audio block, so a
    # parameter written in the same breath would be overwritten by the patch.
    patches = _plan_patches(project, lock)
    report.operations += len(patches)
    if patches:
        result = client.apply(patches, revision, "pulang push: patches")
        revision = result["revision"]
        client.flush_plugins()
        state = DawState(client.projection())

    selectors, parameters = _plan_parameters(project, lock, state, report)
    parameters.extend(_plan_sounds(project, lock, assets))
    report.operations += len(selectors) + len(parameters)
    if selectors:
        result = client.apply(selectors, revision, "pulang push: plugin modes")
        revision = result["revision"]
        client.flush_plugins()
    if parameters:
        result = client.apply(parameters, revision, "pulang push: parameters and automation")
        revision = result["revision"]
    _record_parameters(project, lock)

    report.revision = revision
    song.save_lock(lock)
    song.save_overrides(overrides)
    return report
