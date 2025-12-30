"""
Instrument swapping example - Rapidly prototype with different sounds.

This example shows how to quickly try different instruments on your tracks.
The key insight: MIDI program numbers (0-127) map to General MIDI instruments.
"""

from pypulang import *

# General MIDI instrument numbers (0-indexed)
# Full list: https://en.wikipedia.org/wiki/General_MIDI#Program_change_events

INSTRUMENTS = {
    # Piano
    "acoustic_grand": 0,
    "bright_acoustic": 1,
    "electric_grand": 2,
    "honky_tonk": 3,
    "electric_piano_1": 4,
    "electric_piano_2": 5,
    "harpsichord": 6,
    "clavinet": 7,

    # Chromatic Percussion
    "celesta": 8,
    "glockenspiel": 9,
    "music_box": 10,
    "vibraphone": 11,
    "marimba": 12,
    "xylophone": 13,

    # Organ
    "drawbar_organ": 16,
    "percussive_organ": 17,
    "rock_organ": 18,
    "church_organ": 19,

    # Guitar
    "acoustic_guitar_nylon": 24,
    "acoustic_guitar_steel": 25,
    "electric_guitar_jazz": 26,
    "electric_guitar_clean": 27,
    "electric_guitar_muted": 28,
    "overdriven_guitar": 29,
    "distortion_guitar": 30,

    # Bass
    "acoustic_bass": 32,
    "electric_bass_finger": 33,
    "electric_bass_pick": 34,
    "fretless_bass": 35,
    "slap_bass_1": 36,
    "slap_bass_2": 37,
    "synth_bass_1": 38,
    "synth_bass_2": 39,

    # Strings
    "violin": 40,
    "viola": 41,
    "cello": 42,
    "contrabass": 43,
    "tremolo_strings": 44,
    "pizzicato_strings": 45,
    "orchestral_harp": 46,
    "timpani": 47,
    "string_ensemble_1": 48,
    "string_ensemble_2": 49,
    "synth_strings_1": 50,
    "synth_strings_2": 51,

    # Brass
    "trumpet": 56,
    "trombone": 57,
    "tuba": 58,
    "muted_trumpet": 59,
    "french_horn": 60,
    "brass_section": 61,
    "synth_brass_1": 62,
    "synth_brass_2": 63,

    # Reed
    "soprano_sax": 64,
    "alto_sax": 65,
    "tenor_sax": 66,
    "baritone_sax": 67,
    "oboe": 68,
    "english_horn": 69,
    "bassoon": 70,
    "clarinet": 71,

    # Pipe
    "piccolo": 72,
    "flute": 73,
    "recorder": 74,
    "pan_flute": 75,

    # Synth Lead
    "lead_square": 80,
    "lead_sawtooth": 81,
    "lead_calliope": 82,
    "lead_chiff": 83,
    "lead_charang": 84,
    "lead_voice": 85,
    "lead_fifths": 86,
    "lead_bass_lead": 87,

    # Synth Pad
    "pad_new_age": 88,
    "pad_warm": 89,
    "pad_polysynth": 90,
    "pad_choir": 91,
    "pad_bowed": 92,
    "pad_metallic": 93,
    "pad_halo": 94,
    "pad_sweep": 95,
}


def create_song(bass_instrument=33, keys_instrument=0):
    """
    Create a song with specified instruments.

    Args:
        bass_instrument: MIDI program number for bass (default: electric bass finger)
        keys_instrument: MIDI program number for keys (default: acoustic grand piano)
    """
    with piece(tempo=110, key="A minor") as p:
        verse = p.section("verse", bars=8)
        verse.harmony(i, VI, III, VII, i, VI, III, VII)
        verse.track("bass", role=Role.BASS, instrument=bass_instrument).pattern(root_eighths).octave(-2)
        verse.track("keys", role=Role.HARMONY, instrument=keys_instrument).pattern(arp.up().rate(1/8))

        chorus = p.section("chorus", bars=8)
        chorus.harmony(VI, VII, i, i, VI, VII, i, i)
        chorus.track("bass", role=Role.BASS, instrument=bass_instrument).pattern(root_quarters).octave(-2)
        chorus.track("keys", role=Role.HARMONY, instrument=keys_instrument).pattern(block_chords)

        p.form([verse, chorus, verse, chorus])

    return p


# Try different instrument combinations
def demo_instrument_swap():
    print("Creating versions with different instruments...\n")

    # Version 1: Classic - Piano and Acoustic Bass
    p1 = create_song(bass_instrument=INSTRUMENTS["acoustic_bass"],
                     keys_instrument=INSTRUMENTS["acoustic_grand"])
    p1.save_midi("v1_classic.mid")
    print("v1_classic.mid - Piano + Acoustic Bass")

    # Version 2: Jazz - Electric Piano and Fretless Bass
    p2 = create_song(bass_instrument=INSTRUMENTS["fretless_bass"],
                     keys_instrument=INSTRUMENTS["electric_piano_1"])
    p2.save_midi("v2_jazz.mid")
    print("v2_jazz.mid - Electric Piano + Fretless Bass")

    # Version 3: Synth - Synth Pad and Synth Bass
    p3 = create_song(bass_instrument=INSTRUMENTS["synth_bass_1"],
                     keys_instrument=INSTRUMENTS["pad_warm"])
    p3.save_midi("v3_synth.mid")
    print("v3_synth.mid - Warm Pad + Synth Bass")

    # Version 4: Orchestral - Strings and Cello
    p4 = create_song(bass_instrument=INSTRUMENTS["cello"],
                     keys_instrument=INSTRUMENTS["string_ensemble_1"])
    p4.save_midi("v4_orchestral.mid")
    print("v4_orchestral.mid - String Ensemble + Cello")

    # Version 5: Rock - Overdriven Guitar and Pick Bass
    p5 = create_song(bass_instrument=INSTRUMENTS["electric_bass_pick"],
                     keys_instrument=INSTRUMENTS["overdriven_guitar"])
    p5.save_midi("v5_rock.mid")
    print("v5_rock.mid - Overdriven Guitar + Pick Bass")

    print("\nDone! Open these MIDI files in your DAW or play with a synth.")


if __name__ == "__main__":
    demo_instrument_swap()
