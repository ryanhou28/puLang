"""MIDI files from the `event` dialect."""

from __future__ import annotations

from fractions import Fraction

import mido
from xdsl.dialects.builtin import ModuleOp

from pypulang.compiler.dialects import event

DEFAULT_TICKS_PER_BEAT = 480


def _stream(module: ModuleOp) -> event.StreamOp:
    for op in module.body.block.ops:
        if isinstance(op, event.StreamOp):
            return op
    raise ValueError("Expected an event.stream")


def _track(track: event.TrackOp, ticks_per_beat: int) -> mido.MidiTrack:
    midi = mido.MidiTrack()
    midi.append(mido.MetaMessage("track_name", name=track.track.data, time=0))
    # GM puts percussion on channel 10, which is 9 counted from zero.
    channel = 9 if track.role.data == "rhythm" else 0

    messages: list[tuple[int, str, int, int]] = []
    for note in track.notes():
        start = int(note.start.data * ticks_per_beat)
        end = int((note.start.data + note.dur.data) * ticks_per_beat)
        pitch = max(0, min(127, note.pitch.value.data))
        velocity = max(0, min(127, note.vel.value.data))
        messages.append((start, "note_on", pitch, velocity))
        messages.append((end, "note_off", pitch, 0))
    # At the same tick a note ends before the next begins.
    messages.sort(key=lambda m: (m[0], 0 if m[1] == "note_off" else 1))

    now = 0
    for tick, kind, pitch, velocity in messages:
        midi.append(
            mido.Message(kind, note=pitch, velocity=velocity, time=tick - now, channel=channel)
        )
        now = tick
    midi.append(mido.MetaMessage("end_of_track", time=0))
    return midi


def event_to_midi(module: ModuleOp, ticks_per_beat: int = DEFAULT_TICKS_PER_BEAT) -> mido.MidiFile:
    """A MIDI file for an `event` module."""
    stream = _stream(module)
    midi = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    conductor = mido.MidiTrack()
    midi.tracks.append(conductor)

    now = 0
    tempos = [(t.at.data, t.bpm.value.data, "tempo") for t in stream.tempos()]
    meters = []
    last = None
    for section in stream.sections():
        if section.meter.data != last:
            meters.append((section.at.data, section.meter.data, "meter"))
            last = section.meter.data
    for at, value, kind in sorted(tempos + meters, key=lambda e: (e[0], e[2] == "meter")):
        tick = int(Fraction(at) * ticks_per_beat)
        if kind == "tempo":
            conductor.append(
                mido.MetaMessage("set_tempo", tempo=int(60_000_000 / value), time=tick - now)
            )
        else:
            conductor.append(
                mido.MetaMessage(
                    "time_signature",
                    numerator=value.numerator,
                    denominator=value.denominator,
                    clocks_per_click=24,
                    notated_32nd_notes_per_beat=8,
                    time=tick - now,
                )
            )
        now = tick
    conductor.append(mido.MetaMessage("end_of_track", time=0))

    for track in stream.tracks():
        midi.tracks.append(_track(track, ticks_per_beat))
    return midi
