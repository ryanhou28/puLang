"""
Lantern Rain: a slow jazz-pop ballad in F minor, after the dramatic ballads of
Sheena Ringo and Tokyo Jihen. A muted trumpet sings over piano and strings; the
tenor sax answers in the second verse and takes the bridge.

The verse walks the line cliche down (F, E, Eb, D) under a two-bar question
stated three times; the chorus hook rides a falling chain of roots
(Db, C, Bb, A) and climbs for its third statement. The intro and the bridge
keep their own slower tempo and end on a held altered dominant; the last chorus
comes back a semitone up and broadens into a short outro that slows to a stop.

    pulang render examples/songs/lantern_rain.py -o lantern_rain.wav
"""

from pypulang import *
from pypulang.compiler.passes.perform import Dynamics, Humanize, LayBack, Legato, Phrasing
from pypulang.sounds import FUSION_GAINS, eq, sampler
from pypulang.sounds.instruments import sampled

KICK, SNARE, XSTICK, PEDAL, RIDE, CRASH = 36, 38, 37, 44, 51, 49
TOM_HIGH, TOM_LOW = 50, 45
KIT_NOTES = {"snare": SNARE, "kick": KICK, "tom_high": TOM_HIGH, "tom_low": TOM_LOW, "crash": CRASH}
KIT = "samples/jazz"

# The lead's ideas, in degrees of F minor (natural minor: 6 is Db, 7 is Eb).
MOTIFS = {
    # The verse's question: up from the low fifth through the tonic, and a held ninth.
    "ask": "r/8 5,/8 1/8 3/8 5/4. 4/8 | 2/2. r/4",
    # Its answer: a run down from the octave onto the fifth, held.
    "fall": "1'/8 7 6 5 4/4 3/8 4 | 5/1",
    # The tenor's replies in the second verse's held notes.
    "echo": "r/2 5/8 3/8 1/4",
    "echo2": "r/2 1'/8 5/8 4/4",
    "echo3": "r/2 #3/8 5/8 b7/8 2'/8",
    # The pre-chorus climbs a step each bar, then peaks.
    "rise": "r/8 4/8 5 6 1'/2",
    "peak": "4/4. 3/8 2/2",
    # The chorus hook: up to the third and hung across the bar, then down the altered dominant.
    "hook": "r/8 1/8 2/8 3/4~ 3/8 2/8 1/8 | 7,/4. 6,/8 5,/2",
    # The chorus's last two bars: down the scale to the second, then the leading tone.
    "close": "1'/4 7/8 6/8 5/4 4/8 3/8 | 2/2 #7,/2",
    # The bridge, on the tenor: the Neapolitan's root, then up to the leading tone.
    "plea": "r/8 6,/8 1/8 3/8 b2/2 | 1/1",
    "lift": "r/8 4/8 6/8 1'/8 7/2 | 6/2 #7/2",
    # The last word.
    "home": "r/8 1'/8 2'/8 3'/4. 2'/8 1'/8 | 6/4 5/4 #7,/2 | 1/1",
}

VERSE_CHART = "Fm9 | Fm(maj7)/E | Fm7/Eb | Bb9/D | Dbmaj7 | Gm7b5 C7b9 | Fm9 Fm7/Eb | Dbmaj7 C7sus4"
VERSE_LINE = "ask; ask end 3; ask +2; fall"
CHORUS_CHART = "Dbmaj9 | C7alt | Bbm9 | A7alt | Abmaj9 | Gm7b5 C7b9 | Fm9 Dbmaj7 | Gm7b5 C7alt"
CHORUS_LINE = "hook; hook -2 end 2; hook +1 ^; close"


def drum(section, name, cell, pitch, velocity):
    section.track(name, role=Role.RHYTHM).pattern(grid(cell=cell, pitch=pitch)).velocity(velocity)


def band(section, piano=0.3, bass_cell="x-------x-------", piano_velocity=70, degrees="1 5"):
    """Piano comping and a two-feel bass; on slash chords the bass keeps to the written bass note."""
    section.track("piano", role=Role.HARMONY).pattern(comp(density=piano)).voicing(
        "rootless", 53, 74
    ).velocity(piano_velocity)
    section.track("bass", role=Role.BASS).pattern(
        riff(cell=bass_cell, degrees=degrees, base=41, gate=0.9)
    ).velocity(92)


def strings(section, cell="x-------x-------", velocity=64, low=48, high=84):
    section.track("strings", role=Role.HARMONY).pattern(hits(cell=cell)).voicing(
        "wide", low, high
    ).velocity(velocity)


def fill(section, name, beats, every=None, velocity=90):
    section.fill(
        name, beats=beats, every=every, keep=("pedal",), pitches=KIT_NOTES, velocity=velocity
    )


with piece(tempo=78, key="F minor", title="Lantern Rain") as song:
    for name, notes in MOTIFS.items():
        song.motif(name, notes)

    # --- How it sounds -------------------------------------------------------
    glue = device("glue", "compressor")
    glue.params.update(
        {"Threshold": 0.35, "Ratio": 0.35, "Attack": 0.15, "Release": 0.4, "Output gain": 0.1}
    )
    song.rack("master", glue)
    verb = device("reverb", "reverb")
    verb.params.update({"Room Size": 0.7, "Dry Level": 0.0, "Wet Level": 0.5})
    song.rack("verb", verb, volume=0.7)

    # The mute's loud recordings are bright: a shelf takes the edge off above 2.5 kHz.
    song.rack(
        "trumpet",
        sampled("horn", "muted_trumpet", gain_db=5),
        eq(high=(2500, -7)),
        volume=0.8,
        pan=0.05,
        sends={"verb": 0.3},
    )
    song.rack(
        "sax", sampled("sax", "tenor_sax", gain_db=2), volume=0.64, pan=-0.2, sends={"verb": 0.3}
    )
    song.rack(
        "piano", sampled("piano", "piano", gain_db=-2), volume=0.6, pan=-0.1, sends={"verb": 0.25}
    )
    song.rack("bass", sampled("bass", "upright_bass", gain_db=-4), volume=0.72)
    song.rack("strings", sampled("str", "strings"), volume=0.5, sends={"verb": 0.5})
    # Vibes played with the damper, each note let go over half a second, and less
    # reverb: left to ring under the intro's chords they blurred into the band.
    song.rack(
        "vibes",
        sampled("vib", "vibes", one_shot=False, release_ms=500),
        volume=0.5,
        pan=0.3,
        sends={"verb": 0.25},
    )
    for name, file, key, gain_db, volume in [
        ("ride", "ride.wav", RIDE, FUSION_GAINS["ride"] + 6, 0.5),
        ("pedal", "hihat-pedal.wav", PEDAL, FUSION_GAINS["hat"] - 2, 0.45),
        ("kick", "kick.wav", KICK, FUSION_GAINS["kick"] - 2, 0.55),
        ("snare", "snare.wav", SNARE, FUSION_GAINS["snare"], 0.5),
        ("xstick", "cross-stick.wav", XSTICK, FUSION_GAINS["snare"], 0.45),
        ("crash", "crash.wav", CRASH, FUSION_GAINS["ride"], 0.45),
        ("tom_high", "tom-high.wav", TOM_HIGH, FUSION_GAINS["snare"] - 1, 0.45),
        ("tom_low", "tom-low.wav", TOM_LOW, FUSION_GAINS["snare"] - 1, 0.45),
    ]:
        song.rack(name, sampler("kit", {key: f"{KIT}/{file}"}, gain_db=gain_db), volume=volume)

    # --- Intro: slower, vibes hinting at the hook over piano and strings ------
    intro = song.section("intro", bars=4, tempo=66)
    intro.chart("Dbmaj9 | C7alt | Bbm9 | Gm7b5 C7alt")
    intro.track("vibes", role=Role.MELODY).melody("hook; hook -2 end 2", low=63, high=84).velocity(
        64
    )
    intro.track("piano", role=Role.HARMONY).pattern(hits(cell="x...x...x...x...", gate=0.9)).voicing(
        "rootless", 53, 74
    ).velocity(60)
    intro.track("bass", role=Role.BASS).pattern(
        riff(cell="x---------------", degrees="1", base=41, gate=0.95)
    ).velocity(80)
    strings(intro, cell="x---------------", velocity=56)
    # Easing into the altered dominant and holding it before the verse sets the tempo.
    intro.ritardando(to=58, bars=1).fermata(4, beat=2, hold=2.5, beats=2)

    # --- Verse: the line cliche under the question ---------------------------
    verse = song.section("verse", bars=8)
    verse.chart(VERSE_CHART)
    verse.track("trumpet", role=Role.MELODY).melody(VERSE_LINE, low=58, high=76)
    band(verse, piano=0.3, degrees="1")
    strings(verse, velocity=48)
    drum(verse, "ride", "x...x...x...x...", RIDE, 56)
    drum(verse, "pedal", "....x.......x...", PEDAL, 60)
    drum(verse, "xstick", "............x...", XSTICK, 54)
    drum(verse, "kick", "x.........x.....", KICK, 42)
    fill(verse, "setup", beats=1, velocity=70)

    # --- Pre-chorus: climbing, strings swelling ------------------------------
    pre = song.section("pre", bars=4)
    pre.chart("Bbm9 | Eb13 | Abmaj9 Dbmaj9 | Gm7b5 C7b9")
    pre.track("trumpet", role=Role.MELODY).melody("rise; rise +1; rise +2; peak", low=60, high=82)
    band(pre, piano=0.45, bass_cell="x-------x---x---")
    strings(pre, velocity=70)
    drum(pre, "ride", "x...x...x...x...", RIDE, 64)
    drum(pre, "pedal", "....x.......x...", PEDAL, 64)
    drum(pre, "snare", "................ ..........o..... ......o.....o... ..o...o...o.o...", SNARE, 58)
    drum(pre, "kick", "x.......x.......", KICK, 54)
    fill(pre, "tom run", beats=2, velocity=88)

    # --- Chorus: the hook over the falling roots -----------------------------
    chorus = song.section("chorus", bars=8)
    chorus.chart(CHORUS_CHART)
    chorus.track("trumpet", role=Role.MELODY).melody(CHORUS_LINE, low=63, high=84).velocity(84)
    band(chorus, piano=0.55, bass_cell="x-------x---x---", piano_velocity=76)
    strings(chorus, velocity=76, low=52, high=86)
    drum(chorus, "ride", "x...x.x.x...x.x.", RIDE, 70)
    drum(chorus, "pedal", "....x.......x...", PEDAL, 68)
    drum(chorus, "snare", "............x...", SNARE, 62)
    drum(chorus, "kick", "x.....x...x.....", KICK, 62)
    drum(chorus, "crash", "x" + "." * 127, CRASH, 90)
    fill(chorus, "setup", beats=1, velocity=82)

    # --- Verse 2: the tenor answers in the held notes ------------------------
    verse2 = song.section("verse2", bars=8)
    verse2.chart(VERSE_CHART)
    verse2.track("trumpet", role=Role.MELODY).melody(VERSE_LINE, low=58, high=76)
    verse2.track("sax", role=Role.MELODY).melody(
        "rest 1; echo; rest 1; echo2; rest 1; echo3; rest 1; rest 1", low=50, high=67
    ).velocity(74)
    band(verse2, piano=0.4, bass_cell="x-------x---x---", degrees="1")
    strings(verse2, velocity=52)
    verse2.track("vibes", role=Role.HARMONY).pattern(hits(cell="x.......x.......", gate=0.5)).voicing(
        "quartal", 58, 84
    ).velocity(46)
    drum(verse2, "ride", "x...x.x.x...x.x.", RIDE, 60)
    drum(verse2, "pedal", "....x.......x...", PEDAL, 62)
    drum(verse2, "xstick", "............x...", XSTICK, 56)
    drum(verse2, "kick", "x.........x.....", KICK, 46)
    fill(verse2, "snare roll", beats=1, velocity=80)

    # --- Bridge: its own slower tempo, the tenor over the Neapolitan ---------
    bridge = song.section("bridge", bars=4, tempo=64)
    bridge.chart("Gbmaj7#11 | Fm9 | Ebm9 Ab13 | Dbmaj9 C7alt")
    bridge.track("sax", role=Role.MELODY).melody("plea; lift", low=58, high=78).velocity(84)
    bridge.track("piano", role=Role.HARMONY).pattern(hits(cell="x.......x.......", gate=0.95)).voicing(
        "drop2", 53, 76
    ).velocity(58)
    bridge.track("bass", role=Role.BASS).pattern(
        riff(cell="x-------x-------", degrees="1", base=41, gate=0.95)
    ).velocity(78)
    strings(bridge, velocity=62)
    # Slowing, then the leading tone held over the altered chord before the last chorus.
    bridge.ritardando(to=56, bars=2).fermata(4, beat=2, hold=2.5, beats=2)

    # --- Chorus 2: as the first, broadening into the bridge's tempo ----------
    chorus2 = chorus.transform("chorus2")
    chorus2.ritardando(to=64, bars=1)

    # --- Last chorus, a semitone up, broadening at the end -------------------
    chorus_last = chorus.transform("chorus_last", transpose=1)
    chorus_last.track("sax", role=Role.MELODY).melody(CHORUS_LINE, low=51, high=72).velocity(80)
    chorus_last.ritardando(to=64, bars=2)

    # --- Outro: home, slowing to a held last chord ---------------------------
    outro = song.section("outro", bars=3, key="F# minor", tempo=62)
    outro.chart("Dmaj9 | G#m7b5 C#7alt | F#m(maj9)")
    outro.track("trumpet", role=Role.MELODY).melody("home", low=64, high=81)
    outro.track("piano", role=Role.HARMONY).pattern(hits(cell="x-------x-------")).voicing(
        "rootless", 54, 75
    ).velocity(62)
    outro.track("bass", role=Role.BASS).pattern(
        riff(cell="x-------x-------", degrees="1", base=42, gate=0.95)
    ).velocity(80)
    strings(outro, velocity=66, low=49, high=85)
    drum(outro, "ride", "x...x...x...x... x...x...x...x... x...............", RIDE, 52)
    outro.ritardando(to=52, bars=2, at=2).fermata(3, hold=2, beats=4)

    song.form([intro, verse, pre, chorus, verse2, chorus2, bridge, chorus_last, outro])

LEADS = ("trumpet", "sax", "vibes")
DRUMS = ("ride", "pedal", "kick", "snare", "xstick", "crash", "tom_high", "tom_low")

pipeline = {
    "event": [
        Dynamics(
            marks=(
                ("intro", "p"),
                ("verse", "mp"),
                ("pre", "p<f"),
                ("chorus", "f"),
                ("verse2", "mp"),
                ("chorus2", "f"),
                ("bridge", "pp<mp"),
                ("chorus_last", "ff"),
                ("outro", "mf>pp"),
            )
        ),
        Phrasing(depth=18, ending=10, tracks=LEADS),
        Legato(overlap=6, max_gap="1/4", tracks=("trumpet", "sax")),
        LayBack(ticks=24, tracks=("trumpet",)),
        LayBack(ticks=18, tracks=("sax",)),
        LayBack(ticks=10, tracks=("piano",)),
        Humanize(timing=8, velocity=5, seed="lantern rain", tracks=("piano", "bass", *LEADS)),
        Humanize(timing=5, velocity=6, seed="lantern rain drums", tracks=DRUMS),
    ]
}
