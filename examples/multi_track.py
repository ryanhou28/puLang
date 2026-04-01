"""
Multi-track pyPuLang example - Bass and keys with different patterns.
"""

from pypulang import *

with piece(tempo=120, key="G major") as p:
    # Intro - simple arpeggios
    intro = p.section("intro", bars=4)
    intro.harmony((I, 2), (IV, 2))
    intro.track("keys").pattern(arp.up().rate(1/8))

    # Verse - full arrangement
    verse = p.section("verse", bars=8)
    verse.harmony(I, vi, IV, V, I, vi, IV, V)
    verse.track("bass", role=Role.BASS).pattern(root_eighths).octave(-2)
    verse.track("keys", role=Role.HARMONY).pattern(block_chords)

    # Set form: intro -> verse -> verse
    p.form([intro, verse, verse])

p.save_midi("multi_track.mid")
print("Created multi_track.mid")
