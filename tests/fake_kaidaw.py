"""
A stand-in for a kaiDAW server, speaking the same transport.

The sync tests run against this and against the real engine with the same
assertions, which is what keeps it honest. It models the behaviour puLang relies
on, including the sharp edges: a note sent with an unknown id is created, and a
stale `baseRevision` changes nothing.
"""

from __future__ import annotations

import copy
from typing import Any
from urllib.parse import parse_qs, urlparse


class FakeKaidaw:
    def __init__(self) -> None:
        self.next_id = 1
        self.revision = 0
        self.tempo_map: list[dict[str, Any]] = [{"at": 0, "bpm": 120.0}]
        self.meter_map: list[dict[str, Any]] = [{"at": 0, "numerator": 4, "denominator": 4}]
        self.markers: list[dict[str, Any]] = []
        self.tracks: list[dict[str, Any]] = []
        self.clips: list[dict[str, Any]] = []
        self.plugins: dict[str, dict[str, Any]] = {}
        self.history: list[dict[str, Any]] = []
        self.saved: dict[str, dict[str, Any]] = {}
        self.flushes = 0
        self.master: dict[str, Any] = {
            "id": "master",
            "isMaster": True,
            "name": "Master",
            "pluginIds": [],
            "volume": 1.0,
            "pan": 0.0,
        }
        self._create_track("Track 1", False)

    def _mint(self, prefix: str) -> str:
        self.next_id += 1
        return f"{prefix}-{self.next_id}"

    def _snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(
            {
                "tempo_map": self.tempo_map,
                "meter_map": self.meter_map,
                "markers": self.markers,
                "tracks": self.tracks,
                "master": self.master,
                "clips": self.clips,
                "plugins": self.plugins,
            }
        )

    def _restore(self, snapshot: dict[str, Any]) -> None:
        for name, value in copy.deepcopy(snapshot).items():
            setattr(self, name, value)

    def _plugin(self, name: str, parameters: list[str], utility: bool = False) -> str:
        plugin_id = self._mint("plugin")
        self.plugins[plugin_id] = {
            "id": plugin_id,
            "name": name,
            "utility": utility,
            "parameters": parameters,
            "parameterNames": [p.title() for p in parameters],
            "parameterValues": dict.fromkeys(parameters, 0.5),
            "automation": {},
            "state": "",
        }
        return plugin_id

    def _create_track(self, name: str, with_instrument: bool) -> str:
        track_id = self._mint("track")
        chain = [
            self._plugin("Volume & Pan Plugin", ["volume", "pan"], True),
            self._plugin("Level Meter", [], True),
        ]
        if with_instrument:
            chain.insert(0, self._plugin("4OSC", ["filterFreq", "masterLevel"]))
        self.tracks.append(
            {
                "id": track_id,
                "name": name,
                "isMaster": False,
                "muted": False,
                "soloed": False,
                "volume": 0.740818202495575,
                "pan": 0.0,
                "color": "",
                "pluginIds": chain,
            }
        )
        return track_id

    def _track(self, track_id: str) -> dict[str, Any]:
        if track_id == "master":
            return self.master
        for track in self.tracks:
            if track["id"] == track_id:
                return track
        raise KeyError(f"unknown track {track_id}")

    def _clip(self, clip_id: str) -> dict[str, Any]:
        for clip in self.clips:
            if clip["id"] == clip_id:
                return clip
        raise KeyError(f"unknown clip {clip_id}")

    def _resolve(self, value: Any, aliases: dict[str, str]) -> Any:
        if isinstance(value, str) and value.startswith("$"):
            return aliases[value]
        return value

    def _note(self, wire: dict[str, Any]) -> dict[str, Any]:
        note = dict(wire)
        note["id"] = self._mint("note")
        return note

    def _apply_one(self, op: dict[str, Any], aliases: dict[str, str]) -> None:
        kind = op["type"]
        resolve = lambda field: self._resolve(op[field], aliases)  # noqa: E731
        if kind == "SetTempoMap":
            self.tempo_map = [dict(p) for p in op["points"]]
            if "meters" in op:
                self.meter_map = [dict(m) for m in op["meters"]]
        elif kind == "SetMarkers":
            self.markers = [dict(m) for m in op["markers"]]
        elif kind == "RestorePluginState":
            self.plugins[resolve("pluginId")]["state"] = op["state"]
        elif kind == "SetControllerPoints":
            clip = self._clip(resolve("clipId"))
            clip.setdefault("controllers", {})[op["controller"]] = [dict(p) for p in op["points"]]
        elif kind == "CreateTrack":
            aliases[op["alias"]] = self._create_track(op["name"], op.get("withInstrument", False))
        elif kind == "SetTrackState":
            track = self._track(resolve("trackId"))
            track.update({k: v for k, v in op.items() if k not in ("type", "trackId")})
        elif kind == "AddPlugin":
            plugin_id = self._plugin(op["identifier"], ["cutoff", "resonance"])
            chain = self._track(resolve("trackId"))["pluginIds"]
            # As kaiDAW does: just before the fader, so the fader still controls it.
            fader = next(
                (i for i, p in enumerate(chain) if self.plugins[p]["name"].startswith("Volume")),
                len(chain),
            )
            chain.insert(fader, plugin_id)
            aliases[op["alias"]] = plugin_id
        elif kind == "MovePlugin":
            plugin_id = resolve("pluginId")
            for track in [*self.tracks, self.master]:
                if plugin_id in track["pluginIds"]:
                    track["pluginIds"].remove(plugin_id)
                    track["pluginIds"].insert(op["index"], plugin_id)
        elif kind == "RemovePlugin":
            plugin_id = resolve("pluginId")
            for track in self.tracks:
                if plugin_id in track["pluginIds"]:
                    track["pluginIds"].remove(plugin_id)
            del self.plugins[plugin_id]
        elif kind == "SetPluginParameter":
            self.plugins[resolve("pluginId")]["parameterValues"][op["parameterId"]] = op["value"]
        elif kind == "SetAutomationPoints":
            self.plugins[resolve("pluginId")]["automation"][op["parameterId"]] = op["points"]
        elif kind == "CreateClip":
            clip_id = self._mint("clip")
            self.clips.append(
                {
                    "id": clip_id,
                    "trackId": resolve("trackId"),
                    "name": op["name"],
                    "start": op["start"],
                    "length": op["length"],
                    "muted": False,
                    "notes": [self._note(n) for n in op.get("notes", [])],
                }
            )
            aliases[op["alias"]] = clip_id
        elif kind == "DeleteClip":
            self.clips.remove(self._clip(resolve("clipId")))
        elif kind == "MoveClip":
            clip = self._clip(resolve("clipId"))
            clip["start"] = op["start"]
            if "trackId" in op:
                clip["trackId"] = resolve("trackId")
        elif kind == "ResizeClip":
            self._clip(resolve("clipId"))["length"] = op["length"]
        elif kind == "UpsertNotes":
            clip = self._clip(resolve("clipId"))
            for wire in op["notes"]:
                for existing in clip["notes"]:
                    if existing["id"] == wire.get("id"):
                        existing.update(wire)
                        break
                else:
                    clip["notes"].append(self._note(wire))
        elif kind == "DeleteNotes":
            clip = self._clip(resolve("clipId"))
            clip["notes"] = [n for n in clip["notes"] if n["id"] not in op["noteIds"]]
        elif kind == "CreateSend":
            plugin_id = self._plugin("Send", ["send level"])
            self._track(resolve("fromTrackId"))["pluginIds"].append(plugin_id)
        elif kind == "DeleteTrack":
            track = self._track(resolve("trackId"))
            self.tracks.remove(track)
            self.clips = [c for c in self.clips if c["trackId"] != track["id"]]
        else:
            raise ValueError(f"fake does not model {kind}")

    def request(self, method: str, path: str, body: Any = None) -> Any:
        url = urlparse(path)
        if url.path == "/health":
            return {"ok": True, "engine": "fake"}
        if url.path == "/projection":
            level = parse_qs(url.query).get("level", ["summary"])[0]
            projection: dict[str, Any] = {
                "revision": self.revision,
                "level": level,
                "tempoMap": copy.deepcopy(self.tempo_map),
                "meterMap": copy.deepcopy(self.meter_map),
                "markers": copy.deepcopy(self.markers),
                "tracks": copy.deepcopy(self.tracks),
                "master": copy.deepcopy(self.master),
                "clips": copy.deepcopy(self.clips),
                "plugins": copy.deepcopy(list(self.plugins.values())),
            }
            return projection
        if url.path == "/plugin/state":
            plugin_id = parse_qs(url.query)["pluginId"][0]
            if plugin_id not in self.plugins:
                return {"ok": False, "errors": [f"no plugin {plugin_id}"]}
            return {"ok": True, "pluginId": plugin_id, "state": self.plugins[plugin_id]["state"]}
        if url.path == "/apply":
            if body["baseRevision"] != self.revision:
                return {"status": "conflict", "revision": self.revision, "errors": ["stale"]}
            before = self._snapshot()
            aliases: dict[str, str] = {}
            try:
                for op in body["operations"]:
                    self._apply_one(op, aliases)
            except KeyError as error:
                self._restore(before)
                return {"status": "rejected", "revision": self.revision, "errors": [str(error)]}
            self.history.append(before)
            self.revision += 1
            return {"status": "applied", "revision": self.revision, "aliases": aliases}
        if url.path == "/undo":
            self._restore(self.history.pop())
            self.revision += 1
            return {"status": "applied", "revision": self.revision}
        if url.path == "/save":
            self.saved[body["path"]] = self._snapshot()
            return {"tracks": []}
        if url.path == "/flush":
            self.flushes += 1
            return {}
        if url.path == "/open":
            self._restore(self.saved[body["path"]])
            return {"tracks": []}
        raise ValueError(f"fake does not serve {method} {path}")
