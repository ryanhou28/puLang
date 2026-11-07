"""
Afterglow: future bass in Ab, 150 bpm, drums in half time.

Compile and listen:

    pulang render examples/songs/afterglow.py -o afterglow.wav
"""

from pypulang import *
from pypulang.compiler.passes.perform import Humanize, Pump
from pypulang.sounds import cutoff, future_bass_rack


LOOP = "Fm9 | Dbmaj9 | Abmaj9 | Eb13sus4"
TURN = "Fm9 | Dbmaj9 | Bbm9 | Eb7sus4"
BIG_STAB = "x-.x-.x-.x-.x-x-"

VERSE_LINE = """c5/4. ab4/8 bb4/4 c5 | f5/2 eb5/4 c5 | eb5/4. c5/8 ab4/4 g4 | bb4/1 |
                c5/4. ab4/8 bb4/4 c5 | ab5/2 g5/4 eb5 | f5/4. eb5/8 c5/4 ab4 | bb4/2 r/2 |"""

CHOP = """c6/8' ab5' r/16 c6' eb6/8 c6 ab5 f5/4 |
          eb5/8 f5 ab5 c6 bb5/4 ab5/8 f5 |
          g5/8' ab5' r/16 c6' eb6/8 f6 eb6 c6/4 |
          bb5/8 ab5 f5 eb5 r/2 |
          c6/8' ab5' r/16 c6' eb6/8 c6 ab5 f5/4 |
          eb5/8 f5 ab5 c6 eb6/4 f6/8 eb6 |
          c6/8' bb5' r/16 ab5' g5/8 ab5 bb5 c6/4 |
          eb6/2 r/2 |"""


def drums(section, kick, clap="........x.......", hat="x.x.x.x.x.x.xxxx", level=100):
    section.track("kick", role=Role.RHYTHM).pattern(grid(cell=kick, pitch=31)).velocity(level + 20)
    section.track("clap", role=Role.RHYTHM).pattern(grid(cell=clap, pitch=55)).velocity(level)
    section.track("hat", role=Role.RHYTHM).pattern(grid(cell=hat, pitch=60)).velocity(level - 30)


def plucks(section, level=78):
    section.track("pluck", role=Role.HARMONY).pattern(
        riff(cell="x.x.x.x.x.x.x.x.", degrees="1 5 9 3' 5' 3' 9 5", base=56, gate=0.9)
    ).velocity(level)


def pad(section, level=64):
    section.track("pad", role=Role.HARMONY).pattern(
        hits(cell="x---------------", step=1 / 16)
    ).voicing("close", 53, 81).velocity(level)


def sub(section, cell="x-------x-------", level=108):
    section.track("sub", role=Role.BASS).pattern(
        riff(cell=cell, degrees="1", base=33, gate=0.95)
    ).velocity(level)


def stabs(section, cell=BIG_STAB, level=104):
    section.track("chords", role=Role.HARMONY).pattern(hits(cell=cell, step=1 / 16)).voicing(
        "wide", 53, 96
    ).velocity(level)


def build(song, name):
    section = song.section(name, bars=8)
    section.chart(TURN + " | " + LOOP)
    plucks(section, level=86)
    pad(section, level=70)
    section.track("roll", role=Role.RHYTHM).pattern(
        snare_roll(bars=7, pitch=55, rates=["1", "1/2", "1/4", "1/8"])
    ).velocity(104)
    section.track("riser", role=Role.HARMONY).line("c4/1~ c4~ c4~ c4~ c4~ c4~ c4~ r/1", velocity=96)
    section.automate("riser", "synth.A Filter 1 Cutoff", [(0, cutoff(300)), (7, cutoff(11000))])
    section.automate(
        "pad", "synth.A Filter 1 Cutoff", [(0, cutoff(900)), (7, cutoff(6000)), (8, cutoff(6000))]
    )
    return section


with piece(tempo=150, key="Ab major", title="Afterglow") as song:
    future_bass_rack(song)

    intro = song.section("intro", bars=8)
    intro.chart(LOOP)
    plucks(intro, level=64)
    pad(intro, level=56)
    intro.automate("pad", "synth.A Filter 1 Cutoff", [(0, cutoff(500)), (8, cutoff(1800))])

    verse = song.section("verse", bars=16)
    verse.chart(LOOP)
    pad(verse)
    plucks(verse, level=70)
    sub(verse, level=92)
    drums(verse, kick="x...............", hat="x...x...x...x.x.", level=84)
    verse.track("lead", role=Role.MELODY).line(VERSE_LINE + VERSE_LINE, velocity=88)
    verse.automate("pad", "synth.A Filter 1 Cutoff", [(0, cutoff(1800)), (16, cutoff(2600))])

    rise = build(song, "build")

    drop = song.section("drop", bars=16)
    drop.chart(LOOP)
    stabs(drop)
    sub(drop, cell="x-----x---x-----")
    drums(drop, kick="x.....x...x.....")
    drop.track("impact", role=Role.HARMONY).line("c4/1 " + "r/1 " * 15, velocity=110)
    drop.track("chop", role=Role.MELODY).line(CHOP + CHOP, velocity=100)

    breakdown = song.section("break", bars=8)
    breakdown.chart(TURN)
    pad(breakdown, level=66)
    plucks(breakdown, level=70)
    breakdown.track("lead", role=Role.MELODY).line(VERSE_LINE, velocity=84)
    breakdown.automate("pad", "synth.A Filter 1 Cutoff", [(0, cutoff(2600)), (8, cutoff(1400))])

    rise2 = build(song, "build2")

    drop2 = song.section("drop2", bars=16)
    drop2.chart(LOOP + " | " + TURN)
    stabs(drop2, cell="x-.x-.x-.x-.x.x.")
    sub(drop2, cell="x-----x---x---x-")
    drums(drop2, kick="x.....x...x..x..", hat="x.xxx.x.x.xxx.xx", level=104)
    drop2.track("impact", role=Role.HARMONY).line("c4/1 " + "r/1 " * 15, velocity=110)
    drop2.track("chop", role=Role.MELODY).line(CHOP + CHOP, velocity=104)
    drop2.track("pluck", role=Role.HARMONY).pattern(
        riff(cell="x.x.x.x.x.x.x.x.", degrees="1' 5' 9' 3'' 5' 3'' 9' 5'", base=56, gate=0.8)
    ).velocity(70)

    outro = song.section("outro", bars=8)
    outro.chart(LOOP)
    pad(outro, level=60)
    plucks(outro, level=58)
    outro.automate("pad", "synth.A Filter 1 Cutoff", [(0, cutoff(1800)), (8, cutoff(400))])

    song.form([intro, verse, rise, drop, breakdown, rise2, drop2, outro])

pipeline = {
    "event": [
        Pump(
            target="chords",
            trigger="kick",
            level=0.74,
            depth=0.8,
            release="1",
            sections=("drop", "drop2"),
        ),
        Pump(
            target="sub",
            trigger="kick",
            level=0.74,
            depth=0.35,
            release="1/2",
            sections=("drop", "drop2"),
        ),
        Humanize(timing=4, velocity=4, seed="afterglow", tracks=("hat", "pluck")),
    ]
}
