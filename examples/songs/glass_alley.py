"""
Glass Alley: jazz-pop in D minor, after the big-band kayōkyoku of Sheena Ringo
and Tokyo Jihen. Medium swing; a muted trumpet sings the line.

The melody is motifs, written once in scale degrees and developed: the verse
states one idea three times (held, a step down, climbing) and answers it with a
turn onto the harmonic minor's C#. The chorus runs on the IVmaj7-III7-vi-v-I7
progression common in Japanese pop, and its last time comes back a semitone up.

The instruments are samples from two CC0 libraries. Build them first:

    python scripts/get_drum_samples.py
    python scripts/get_instrument_samples.py
    pulang render examples/songs/glass_alley.py -o glass_alley.wav
"""

from pypulang import *
from pypulang.compiler.passes.perform import Dynamics, Humanize, LayBack, Legato, Phrasing, Swing
from pypulang.sounds import FUSION_GAINS, sampler
from pypulang.sounds.instruments import sampled

KICK, SNARE, XSTICK, PEDAL, RIDE, BELL, CRASH = 36, 38, 37, 44, 51, 53, 49
TOM_HIGH, TOM_LOW = 50, 45
# Where each drum the fills name sits, for sections where it keeps no time
KIT_NOTES = {"snare": SNARE, "kick": KICK, "tom_high": TOM_HIGH, "tom_low": TOM_LOW, "crash": CRASH}
KIT = "samples/jazz"

# The lead's ideas, in degrees of D minor. "#7" is the harmonic minor's C#.
MOTIFS = {
    # The verse: a sigh from the fifth down to the tonic, and a held ninth.
    "call": "r/8 5/8 6 5 3/4. 1/8 | 2/2 r/2",
    # Its answer: down from the octave, landing on the leading tone.
    "turn": "r/8 1'/8 7 6 5/4. 3/8 | #7,/2 r/2",
    # The tenor's reply in the verse's gaps.
    "echo": "r/8 5,/8 4, 3,",
    # The pre-chorus climbs a step each bar, then reaches.
    "climb": "r/8 6/8 7 1'/4. r/4",
    "reach": "1'/8 3' 4'/2.",
    # The chorus hook: the #11 over Bbmaj7, then D hung over A7 and let down to C#.
    "hook": "3/4. 2/8 1/4 6,/8 1~ | 1/8 #7,/4. 5,/2",
    "cadence": "1/4 3/4 2/8 1 7,/4 | 6,/4 5,/4 #7,/2",
    # The bridge: a long falling line, and a lift into the key change.
    "lament": "5/2 4/4 3/8 2 | 3/1",
    "lift": "1/8 3 5 1' 3'/2 | 4'/2. r/4",
    # The outro's last note.
    "home": "1/2.~ 1/1",
}

VERSE_CHART = "Dm9 | Dm(maj7)/C# | Dm7/C | Dm6/B | Bbmaj7 | Gm7 C7 | Fmaj7 Em7b5 | A7b9"
VERSE_LINE = "call; call -1; call +2; turn"
CHORUS_CHART = "Bbmaj7 | A7 | Dm7 | Cm7 F7 | Bbmaj7 | A7 | Dm7 | Gm7 A7"
CHORUS_LINE = "hook; hook -2; hook vary 2; cadence"

# Ride, hi-hat pedal on two and four, a feathered kick: a swing kit at rest.
RIDE_TIME = "x...x.x.x...x.x."
TWO_FOUR = "....x.......x..."


def drum(section, name, cell, pitch, velocity):
    section.track(name, role=Role.RHYTHM).pattern(grid(cell=cell, pitch=pitch)).velocity(velocity)


def band(section, piano=0.4, walk=True):
    """Piano comping and bass, the floor every section stands on."""
    section.track("piano", role=Role.HARMONY).pattern(comp(density=piano)).voicing(
        "rootless", 52, 72
    ).velocity(72)
    if walk:
        section.track("bass", role=Role.BASS).pattern(walking_bass(centre=40)).velocity(96)
    else:
        section.track("bass", role=Role.BASS).pattern(
            riff(cell="x.......x.......", degrees="1 5", base=38, gate=0.9)
        ).velocity(96)


def fill(section, name, beats, every=None, velocity=96):
    """A drum fill; the hi-hat foot keeps time through it, as a drummer's would."""
    section.fill(
        name, beats=beats, every=every, keep=("pedal",), pitches=KIT_NOTES, velocity=velocity
    )


def brass(section, cell, velocity=96):
    """Trumpets and trombones hitting together, the trumpets voiced above."""
    section.track("trumpets", role=Role.HARMONY).pattern(hits(cell=cell, gate=0.8)).voicing(
        "drop2", 60, 84
    ).velocity(velocity)
    section.track("bones", role=Role.HARMONY).pattern(hits(cell=cell, gate=0.8)).voicing(
        "shell", 43, 67
    ).velocity(velocity - 6)


with piece(tempo=126, key="D minor", title="Glass Alley") as song:
    for name, notes in MOTIFS.items():
        song.motif(name, notes)

    # --- How it sounds -------------------------------------------------------
    glue = device("glue", "compressor")
    glue.params.update(
        {"Threshold": 0.3, "Ratio": 0.4, "Attack": 0.1, "Release": 0.3, "Output gain": 0.12}
    )
    song.rack("master", glue)
    verb = device("reverb", "reverb")
    verb.params.update({"Room Size": 0.55, "Dry Level": 0.0, "Wet Level": 0.5})
    song.rack("verb", verb, volume=0.7)

    song.rack(
        "trumpet",
        sampled("horn", "muted_trumpet", gain_db=5),
        volume=0.72,
        pan=0.05,
        sends={"verb": 0.25},
    )
    song.rack(
        "sax", sampled("sax", "tenor_sax", gain_db=2), volume=0.62, pan=-0.22, sends={"verb": 0.22}
    )
    song.rack(
        "piano", sampled("piano", "piano", gain_db=-2), volume=0.62, pan=-0.1, sends={"verb": 0.18}
    )
    song.rack("bass", sampled("bass", "upright_bass", gain_db=-4), volume=0.76)
    song.rack("trumpets", sampled("tp", "trumpet_stab"), volume=0.56, pan=0.3, sends={"verb": 0.3})
    song.rack(
        "bones",
        sampled("tb", "trombone_stab", gain_db=4),
        volume=0.56,
        pan=-0.3,
        sends={"verb": 0.3},
    )
    song.rack("strings", sampled("str", "strings"), volume=0.5, sends={"verb": 0.45})
    song.rack("vibes", sampled("vib", "vibes"), volume=0.48, pan=0.35, sends={"verb": 0.35})
    for name, file, key, gain_db, volume in [
        ("ride", "ride.wav", RIDE, FUSION_GAINS["ride"] + 8, 0.6),
        ("bell", "ride-bell.wav", BELL, FUSION_GAINS["ride"], 0.5),
        ("pedal", "hihat-pedal.wav", PEDAL, FUSION_GAINS["hat"] - 2, 0.5),
        ("kick", "kick.wav", KICK, FUSION_GAINS["kick"] - 2, 0.6),
        ("snare", "snare.wav", SNARE, FUSION_GAINS["snare"], 0.55),
        ("xstick", "cross-stick.wav", XSTICK, FUSION_GAINS["snare"], 0.5),
        ("crash", "crash.wav", CRASH, FUSION_GAINS["ride"], 0.5),
        ("tom_high", "tom-high.wav", TOM_HIGH, FUSION_GAINS["snare"] - 1, 0.5),
        ("tom_low", "tom-low.wav", TOM_LOW, FUSION_GAINS["snare"] - 1, 0.5),
    ]:
        song.rack(name, sampler("kit", {key: f"{KIT}/{file}"}, gain_db=gain_db), volume=volume)

    # --- Intro: brass, and the hook's first breath ---------------------------
    intro = song.section("intro", bars=4)
    intro.chart("Bbmaj7 | A7alt | Dm9 | %")
    intro.track("trumpet", role=Role.MELODY).melody("hook first 6; rest 2", low=64, high=81)
    band(intro, piano=0.3, walk=False)
    brass(intro, "x--.....x-.x-... ........x------- ................ ......x-..x-x---")
    intro.track("strings", role=Role.HARMONY).pattern(hits(cell="x---------------")).voicing(
        "wide", 48, 84
    ).velocity(64)
    drum(intro, "ride", RIDE_TIME, RIDE, 72)
    drum(intro, "pedal", TWO_FOUR, PEDAL, 70)
    drum(intro, "crash", "x" + "." * 63, CRASH, 90)
    fill(intro, "setup", beats=1)

    # --- Verse: the line cliché under a sung idea ----------------------------
    verse = song.section("verse", bars=8)
    verse.chart(VERSE_CHART)
    verse.track("trumpet", role=Role.MELODY).melody(VERSE_LINE, low=57, high=74)
    band(verse, piano=0.3, walk=False)
    drum(verse, "ride", RIDE_TIME, RIDE, 64)
    drum(verse, "pedal", TWO_FOUR, PEDAL, 66)
    drum(verse, "xstick", "............x...", XSTICK, 58)
    drum(verse, "kick", "x.......x.......", KICK, 44)
    fill(verse, "setup", beats=1, every=4, velocity=80)

    # --- Pre-chorus: a climb, strings swelling under it ----------------------
    pre = song.section("pre", bars=4)
    pre.chart("Gm9 | Am7 | Bbmaj7 | A7alt")
    pre.track("trumpet", role=Role.MELODY).melody(
        "climb; climb +1; climb +2; reach", low=57, high=79
    )
    band(pre, piano=0.5)
    pre.track("strings", role=Role.HARMONY).pattern(hits(cell="x---------------")).voicing(
        "wide", 48, 84
    ).velocity(80)
    drum(pre, "ride", RIDE_TIME, RIDE, 72)
    drum(pre, "pedal", TWO_FOUR, PEDAL, 70)
    drum(
        pre,
        "snare",
        "........ ......o. ......o. ...o.... ....o..o ......o. ..o..o.. o.o.x.xX",
        SNARE,
        70,
    )
    drum(pre, "kick", "x.......x.......", KICK, 60)
    fill(pre, "tom run", beats=2)

    # --- Chorus: the hook, the band answering --------------------------------
    chorus = song.section("chorus", bars=8)
    chorus.chart(CHORUS_CHART)
    chorus.track("trumpet", role=Role.MELODY).melody(CHORUS_LINE, low=64, high=81)
    # The tenor doubles the line an octave down.
    chorus.track("sax", role=Role.MELODY).melody(CHORUS_LINE, low=52, high=69).velocity(84)
    band(chorus, piano=0.6)
    brass(chorus, "................ ......x-....x-..", velocity=90)
    chorus.track("strings", role=Role.HARMONY).pattern(hits(cell="x-------x-------")).voicing(
        "wide", 52, 86
    ).velocity(72)
    drum(chorus, "ride", RIDE_TIME, RIDE, 80)
    drum(chorus, "pedal", TWO_FOUR, PEDAL, 74)
    drum(chorus, "snare", "....x.......x...", SNARE, 64)
    drum(chorus, "kick", "x.....x...x.....", KICK, 66)
    drum(chorus, "crash", "x" + "." * 127, CRASH, 96)
    fill(chorus, "snare roll", beats=1, every=4, velocity=90)

    # --- Break: stop time ----------------------------------------------------
    brk = song.section("brk", bars=2)
    brk.chart("Bb7#11 | A7alt")
    stops = "x..x..x.....x... ....x.......x.x."
    brass(brk, stops, velocity=104)
    brk.track("bass", role=Role.BASS).pattern(
        riff(cell=stops, degrees="1", base=38, gate=0.5)
    ).velocity(104)
    brk.track("piano", role=Role.HARMONY).pattern(hits(cell=stops, gate=0.5)).voicing(
        "rootless", 52, 72
    ).velocity(84)
    drum(brk, "snare", stops, SNARE, 100)
    drum(brk, "kick", stops, KICK, 92)
    drum(brk, "crash", "x" + "." * 31, CRASH, 100)

    # --- Verse 2: walking now, the tenor answering ---------------------------
    verse2 = song.section("verse2", bars=8)
    verse2.chart(VERSE_CHART)
    verse2.track("trumpet", role=Role.MELODY).melody(VERSE_LINE, low=57, high=74)
    verse2.track("sax", role=Role.MELODY).melody(
        "rest 1; rest 2; echo; rest 1; rest 2; echo -1; rest 1; rest 2; echo +2; rest 1; rest 1",
        low=50,
        high=67,
    ).velocity(80)
    band(verse2, piano=0.45)
    verse2.track("vibes", role=Role.HARMONY).pattern(
        hits(cell="x.......x.......", gate=0.5)
    ).voicing("quartal", 60, 79).velocity(52)
    drum(verse2, "ride", RIDE_TIME, RIDE, 70)
    drum(verse2, "pedal", TWO_FOUR, PEDAL, 70)
    drum(verse2, "snare", "......o. ...o.... ........ ..o...o.", SNARE, 54)
    drum(verse2, "kick", "x.......x.......", KICK, 50)
    fill(verse2, "setup", beats=1, every=4, velocity=84)

    # --- Bridge: half time, strings and vibes, rising to the key change ------
    bridge = song.section("bridge", bars=8)
    bridge.chart("Gm9 | C9sus4 | Fmaj9 | Bbmaj9 | Em7b5 | A7b9 | Dm9 | Bb13")
    bridge.track("trumpet", role=Role.MELODY).melody(
        "lament; lament -1; lament inv; lift", low=55, high=79
    )
    band(bridge, piano=0.2, walk=False)
    bridge.track("strings", role=Role.HARMONY).pattern(hits(cell="x---------------")).voicing(
        "wide", 48, 84
    ).velocity(70)
    bridge.track("vibes", role=Role.HARMONY).pattern(
        hits(cell="x...x...x...x...", gate=0.5)
    ).voicing("quartal", 60, 79).velocity(48)
    drum(bridge, "ride", "x.......x.......", RIDE, 62)
    drum(bridge, "pedal", TWO_FOUR, PEDAL, 60)
    drum(bridge, "kick", "x...............", KICK, 52)
    # A whole bar down the kit into the key change
    fill(bridge, "tom run", beats=4, velocity=100)
    # ...and the band broadens under it, so the key change lands with weight.
    bridge.ritardando(to=112, bars=1)

    # --- Last chorus, a semitone up ------------------------------------------
    chorus_up = chorus.transform("chorus_up", transpose=1)

    # --- Outro: the hook slowed, and home ------------------------------------
    outro = song.section("outro", bars=4, key="Eb minor")
    outro.chart("Bmaj7 | Bb7alt | Ebm(maj9) | %")
    # Slowing into the last chord, then holding it.
    outro.ritardando(to=96, bars=2, at=2).fermata(4, hold=1.5, beats=4)
    outro.track("trumpet", role=Role.MELODY).melody("hook first 5 x2; home", low=64, high=81)
    outro.track("piano", role=Role.HARMONY).pattern(hits(cell="x---------------")).voicing(
        "rootless", 52, 72
    ).velocity(70)
    outro.track("bass", role=Role.BASS).pattern(
        riff(cell="x---------------", degrees="1", base=38)
    ).velocity(90)
    outro.track("strings", role=Role.HARMONY).pattern(hits(cell="x---------------")).voicing(
        "wide", 48, 86
    ).velocity(76)
    brass(outro, "................ ................ x--------------- ................", velocity=84)
    drum(outro, "ride", RIDE_TIME + RIDE_TIME + "x" + "." * 31, RIDE, 66)
    drum(outro, "crash", "." * 32 + "x" + "." * 31, CRASH, 92)

    song.form([intro, verse, pre, chorus, brk, verse2, pre, chorus, bridge, chorus_up, outro])

LEADS = ("trumpet", "sax")
DRUMS = ("ride", "bell", "pedal", "kick", "snare", "xstick", "crash", "tom_high", "tom_low")

pipeline = {
    "event": [
        Swing(ratio="3/5"),
        Dynamics(
            marks=(
                ("intro", "mf"),
                ("verse", "mp"),
                ("pre", "p<f"),
                ("chorus", "f"),
                ("brk", "ff"),
                ("verse2", "mp"),
                ("bridge", "p<mf"),
                ("chorus_up", "ff"),
                ("outro", "f>p"),
            )
        ),
        Phrasing(depth=16, ending=8, tracks=LEADS),
        Legato(overlap=6, max_gap="1/4", tracks=LEADS),
        # The singer and the tenor sit behind the beat, the ride a hair ahead.
        LayBack(ticks=22, tracks=("trumpet",)),
        LayBack(ticks=16, tracks=("sax",)),
        LayBack(ticks=8, tracks=("piano",)),
        LayBack(ticks=-6, tracks=("ride", "bell")),
        Humanize(timing=8, velocity=5, seed="glass alley", tracks=("piano", "bass", *LEADS)),
        Humanize(timing=5, velocity=6, seed="glass alley drums", tracks=DRUMS),
    ]
}
