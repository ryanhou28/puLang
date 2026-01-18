"""
Test drums with DAW routing - best sound quality!

SETUP:
1. Open your DAW (Ableton, FL Studio, Logic, etc.)
2. Create a MIDI track with drums/percussion instrument
3. Set input to "pypulang" virtual MIDI port
4. Run this script
5. Hear professional drum sounds from your DAW!
"""

from pypulang import piece, Role, I, IV, V, vi, rock_beat, root_quarters

with piece(tempo=120, key="C major") as p:
    verse = p.section("verse", bars=8)
    verse.harmony(I, IV, vi, V)
    verse.track("drums", role=Role.RHYTHM).pattern(rock_beat)
    verse.track("bass", role=Role.BASS).pattern(root_quarters).octave(-1)

# List available MIDI ports
print("Available MIDI ports:")
ports = p.list_ports()
for i, port in enumerate(ports):
    print(f"  {i}: {port}")

# Create virtual MIDI port
print("\nCreating virtual MIDI port 'pypulang'...")
print("Connect to this in your DAW!")
p.connect(port="pypulang")

# Play through virtual MIDI
print("\nPlaying... (Ctrl+C to stop)")
print("Your DAW should receive the MIDI notes now.")
p.loop()
