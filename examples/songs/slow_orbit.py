"""
Slow Orbit: jazz fusion in D dorian.

Compile and listen:

    pulang render examples/songs/slow_orbit.py -o slow_orbit.wav
"""

from pypulang import *
from pypulang.compiler.passes.perform import Accent, Bend, Humanize, Swing
from pypulang.pitches import C3, C5, E3, F4, G3
from pypulang.sounds import fusion_drums, fusion_rack

KICK, SNARE, HAT, RIDE = 31, 55, 60, 84

with piece(tempo=116, key="D dorian", title="Slow Orbit") as song:
    fusion_rack(song, kit="samples/jazz")

    # --- Intro: a pedal and a question ---------------------------------------
    intro = song.section("intro", bars=8)
    intro.chart("Dm11 | % | Bbmaj7#11 | Gsus13 | Dm11 | % | Ebmaj7#11 | A7alt")
    intro.track("rhodes", role=Role.HARMONY).pattern(
        hits(cell="x-----.. ..x-.... ........ ........", step=1 / 16, gate=0.9)
    ).voicing("quartal", E3, C5).velocity(62)
    intro.track("pad", role=Role.HARMONY).pattern(
        hits(cell="x---------------", step=1 / 16)
    ).voicing("drop2", G3, 88).velocity(50)
    intro.track("bass", role=Role.BASS).pattern(
        riff(cell="x-----..........", degrees="1", base=38)
    ).velocity(84)
    intro.track("hat", role=Role.RHYTHM).pattern(grid(cell="..x...x...x...x.", pitch=HAT)).velocity(
        46
    )

    # --- A: the head ---------------------------------------------------------
    a = song.section("a", bars=16)
    a.chart(
        """Dm11 | % | Bbmaj9#11 | A7alt
           Dm11 | Fmaj9 | Ebmaj9#11 | A7b13
           Gm11 | C13 | Fmaj9 | Bb13#11
           Em7b5 | A7alt | Dm11 | %""".replace("\n", " | ")
    )
    a.track("lead", role=Role.MELODY).line(
        """r/8 a4/16 c5 d5/8 f5 e5/16 d5 c5/8 a4/4 |
           g5/4. f5/8 e5 d5 c5/4 |
           e5/8. d5/16 c5/8 e5 f5/4 a5 |
           bb5/8 g5 f5 eb5 c#5/4 r |
           r/8 a4/16 c5 d5/8 f5 g5/16 a5 c6/8 a5/4 |
           g5/4. e5/8 c5 a4 g4/4 |
           bb4/8. d5/16 f5/8 a5 g5/4 f5 |
           f5/8 e5 c#5 a4 g4/2 |
           bb4/8 c5 d5 f5 a5/4 g5/8 f5 |
           e5/8 g5 a5 bb5 c6/4. a5/8 |
           g5/4 e5/8 c5 a4/4 g4/8 a4 |
           c5/8 d5 e5 g5 ab5/2 |
           g5/8. f5/16 d5/8 bb4 c5/4 e5 |
           f5/8 eb5 db5 bb4 c5/4 a4 |
           d5/2. r/4 |
           r/1 |""",
        velocity=96,
    )
    a.track("rhodes", role=Role.HARMONY).pattern(
        hits(cell="...x..x...x...x. .x..x.....x..x..", step=1 / 16, gate=0.7)
    ).voicing("rootless", E3, C5).velocity(74)
    a.track("pad", role=Role.HARMONY).pattern(hits(cell="x---------------", step=1 / 16)).voicing(
        "drop2", G3, 88
    ).velocity(44)
    a.track("bass", role=Role.BASS).pattern(
        riff(cell="x..x..x.x.x..x..", degrees="1 1 b7 5 1' 4", base=38, gate=0.8)
    ).velocity(100)
    fusion_drums(a, kick="x..x..x...x..x..", snare="....x..o.o..x..o", hat="X.x.X.x.X.x.X.xo")

    # --- B: seven eight ------------------------------------------------------
    b = song.section("b", bars=8, time_sig="7/8")
    b.chart("Gm9 | % | Ebmaj9#11 | % | Cm9 | F13sus4 | Bbmaj9 | A7alt")
    b.track("lead", role=Role.MELODY).line(
        """g4/8 bb4 d5 f5 a5/4. |
           g5/8 f5 d5 bb4 c5/4. |
           g4/8 bb4 d5 f5 a5/4. |
           bb5/8 a5 f5 d5 c5/4. |
           g4/8 bb4 eb5 g5 d6/4. |
           c6/8 bb5 g5 eb5 d5/4. |
           c5/8 d5 f5 a5 c6/4. |
           bb5/8 g5 f5 eb5 c#5/4. |""",
        velocity=100,
    )
    b.track("rhodes", role=Role.HARMONY).pattern(
        hits(cell="x.x.x..", step=1 / 8, gate=0.6)
    ).voicing("rootless", E3, C5).velocity(78)
    b.track("bass", role=Role.BASS).pattern(
        riff(cell="x.x.x..", step=1 / 8, degrees="1 b7 4", base=38, gate=0.85)
    ).velocity(104)
    fusion_drums(b, step=1 / 8, kick="x.x.x..", snare="..x..x.", hat="xxxxxxx")

    # --- Solo: swing, over walking bass --------------------------------------
    solo = song.section("solo", bars=16)
    solo.chart(
        "Dm9 | G13 | Dm9 | G13 | Bbmaj7 | A7alt | Dm9 | % "
        "| Gm9 | C13 | Fmaj9 | Bbmaj7#11 | Em7b5 | A7alt | Dm9 | A7alt"
    )
    solo.track("lead", role=Role.MELODY).pattern(
        solo_line(low=65, high=89, phrase=2, rest=0.2)
    ).velocity(92)
    solo.track("rhodes", role=Role.HARMONY).pattern(comp(density=0.6)).voicing(
        "rootless", E3, C5
    ).velocity(70)
    solo.track("bass", role=Role.BASS).pattern(walking_bass(centre=41)).velocity(100)
    solo.track("ride", role=Role.RHYTHM).pattern(
        grid(cell="x...x.x.x...x.x.", step=1 / 16, pitch=RIDE)
    ).velocity(78)
    solo.track("hat", role=Role.RHYTHM).pattern(grid(cell="....x.......x...", pitch=HAT)).velocity(
        70
    )
    solo.track("kick", role=Role.RHYTHM).pattern(
        grid(cell="o...o...o...o...", pitch=KICK)
    ).velocity(90)
    solo.track("snare", role=Role.RHYTHM).pattern(
        grid(cell=".......o.....o.. ...o.......o..o.", pitch=SNARE)
    ).velocity(80)

    # --- Outro: back to the pedal --------------------------------------------
    outro = song.section("outro", bars=8)
    outro.chart("Dm11 | % | Bbmaj7#11 | Gsus13 | Dm11 | % | % | %")
    outro.track("rhodes", role=Role.HARMONY).pattern(
        hits(cell="x-----.. ..x-.... ........ ........", step=1 / 16, gate=0.9)
    ).voicing("quartal", E3, C5).velocity(60)
    outro.track("pad", role=Role.HARMONY).pattern(
        hits(cell="x---------------", step=1 / 16)
    ).voicing("drop2", G3, 88).velocity(48)
    outro.track("bass", role=Role.BASS).pattern(
        riff(cell="x-----..........", degrees="1", base=38)
    ).velocity(78)
    outro.track("lead", role=Role.MELODY).line(
        "r/1 | r/1 | r/1 | r/1 | d5/2. r/4 | a4/2 c5/2 | d5/1~ | d5/1 |", velocity=72
    )
    outro.automate("pad", "mix.volume", [(4, 0.6), (8, 0.0)])

    song.form([intro, a, b, a, solo, b, a, outro])

pipeline = {
    "event": [
        Swing(ratio="3/5", sections=("solo",), tracks=("lead", "rhodes", "ride", "hat", "snare")),
        Accent(on=4, off=-3, tracks=("hat",), sections=("a",)),
        Humanize(timing=10, velocity=5, seed="slow orbit", tracks=("rhodes", "bass", "lead")),
        # A scoop into every other long lead note, a semitone up from below.
        Bend(track="lead", kind="scoop", semitones=1, time="1/8", min_length="1/2", every=2),
        Humanize(
            timing=6, velocity=7, seed="slow orbit drums", tracks=("kick", "snare", "hat", "ride")
        ),
    ]
}
