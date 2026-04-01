"""
Minimal pyPuLang example - A simple 4-bar bass line.
"""

from pypulang import *

# Create a piece with tempo and key
with piece(tempo=100, key="C major") as p:
    # Create a 4-bar verse section
    verse = p.section("verse", bars=4)

    # Set the chord progression: I - IV - vi - V (each chord = 1 bar)
    verse.harmony(I, IV, vi, V)

    # Add a bass track playing root notes on quarter beats, 1 octave down
    verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

# Save to MIDI file
p.save_midi("minimal.mid")
print("Created minimal.mid")

# You can also get the MIDI object directly
midi = p.to_midi()
print(f"MIDI has {len(midi.tracks)} tracks")

# Or get the IR for inspection
ir = p.to_ir()
print(f"IR has {len(ir.sections)} section(s) with {len(ir.sections[0].harmony.changes)} chords")
