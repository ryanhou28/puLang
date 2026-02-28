"""Drum sounds and percussion constants mapped to General MIDI drum map.

This module defines constants for drum sounds following the GM Level 1 percussion map.
All drums are on MIDI channel 10, with different pitches representing different drum sounds.

Usage:
    from pypulang import piece, Role
    from pypulang.drums import KICK, SNARE, HIHAT_CLOSED
    from pypulang.pitches import note

    with piece(tempo=120, key="C major") as p:
        verse = p.section("verse", bars=4)
        verse.track("drums", role=Role.RHYTHM).notes([
            (KICK, 1/4), (SNARE, 1/4), (KICK, 1/4), (SNARE, 1/4),
        ])
"""

from pypulang.pitches import Pitch

# ==============================================================================
# Bass Drums
# ==============================================================================

KICK = Pitch(36)       # Acoustic Bass Drum
KICK2 = Pitch(35)      # Bass Drum 1 (alternative)

# ==============================================================================
# Snare Drums
# ==============================================================================

SNARE = Pitch(38)      # Acoustic Snare
SNARE2 = Pitch(40)     # Electric Snare
RIMSHOT = Pitch(37)    # Side Stick / Rim Shot
CLAP = Pitch(39)       # Hand Clap

# ==============================================================================
# Hi-Hats
# ==============================================================================

HIHAT_CLOSED = Pitch(42)   # Closed Hi-Hat
HIHAT_PEDAL = Pitch(44)    # Pedal Hi-Hat
HIHAT_OPEN = Pitch(46)     # Open Hi-Hat

# ==============================================================================
# Toms
# ==============================================================================

TOM_LOW = Pitch(45)    # Low Tom
TOM_MID = Pitch(47)    # Mid Tom
TOM_HIGH = Pitch(50)   # High Tom
TOM_LOW2 = Pitch(41)   # Low Floor Tom
TOM_MID2 = Pitch(43)   # High Floor Tom
TOM_HIGH2 = Pitch(48)  # Hi-Mid Tom

# ==============================================================================
# Cymbals
# ==============================================================================

CRASH = Pitch(49)      # Crash Cymbal 1
CRASH2 = Pitch(57)     # Crash Cymbal 2
RIDE = Pitch(51)       # Ride Cymbal 1
RIDE_BELL = Pitch(53)  # Ride Bell
CHINA = Pitch(52)      # Chinese Cymbal
SPLASH = Pitch(55)     # Splash Cymbal

# ==============================================================================
# Percussion
# ==============================================================================

TAMBOURINE = Pitch(54) # Tambourine
COWBELL = Pitch(56)    # Cowbell
SHAKER = Pitch(70)     # Maracas
VIBRASLAP = Pitch(58)  # Vibraslap
WOODBLOCK_HIGH = Pitch(76)  # High Wood Block
WOODBLOCK_LOW = Pitch(77)   # Low Wood Block
GUIRO_SHORT = Pitch(73)     # Short Guiro
GUIRO_LONG = Pitch(74)      # Long Guiro
CLAVES = Pitch(75)          # Claves
TRIANGLE_MUTE = Pitch(80)   # Mute Triangle
TRIANGLE_OPEN = Pitch(81)   # Open Triangle

# ==============================================================================
# Latin/World Percussion
# ==============================================================================

CONGA_HIGH = Pitch(62)      # Mute Hi Conga
CONGA_HIGH_OPEN = Pitch(63) # Open Hi Conga
CONGA_LOW = Pitch(64)       # Low Conga
BONGO_HIGH = Pitch(60)      # Hi Bongo
BONGO_LOW = Pitch(61)       # Low Bongo
TIMBALE_HIGH = Pitch(65)    # High Timbale
TIMBALE_LOW = Pitch(66)     # Low Timbale
AGOGO_HIGH = Pitch(67)      # High Agogo
AGOGO_LOW = Pitch(68)       # Low Agogo
CABASA = Pitch(69)          # Cabasa
WHISTLE_SHORT = Pitch(71)   # Short Whistle
WHISTLE_LONG = Pitch(72)    # Long Whistle

# ==============================================================================
# Complete GM Drum Map Reference
# ==============================================================================
#
# For reference, here's the complete General MIDI Level 1 percussion map:
#
# 35: Acoustic Bass Drum (KICK2)
# 36: Bass Drum 1 (KICK)
# 37: Side Stick (RIMSHOT)
# 38: Acoustic Snare (SNARE)
# 39: Hand Clap (CLAP)
# 40: Electric Snare (SNARE2)
# 41: Low Floor Tom (TOM_LOW2)
# 42: Closed Hi-Hat (HIHAT_CLOSED)
# 43: High Floor Tom (TOM_MID2)
# 44: Pedal Hi-Hat (HIHAT_PEDAL)
# 45: Low Tom (TOM_LOW)
# 46: Open Hi-Hat (HIHAT_OPEN)
# 47: Low-Mid Tom (TOM_MID)
# 48: Hi-Mid Tom (TOM_HIGH2)
# 49: Crash Cymbal 1 (CRASH)
# 50: High Tom (TOM_HIGH)
# 51: Ride Cymbal 1 (RIDE)
# 52: Chinese Cymbal (CHINA)
# 53: Ride Bell (RIDE_BELL)
# 54: Tambourine (TAMBOURINE)
# 55: Splash Cymbal (SPLASH)
# 56: Cowbell (COWBELL)
# 57: Crash Cymbal 2 (CRASH2)
# 58: Vibraslap (VIBRASLAP)
# 59: Ride Cymbal 2
# 60: Hi Bongo (BONGO_HIGH)
# 61: Low Bongo (BONGO_LOW)
# 62: Mute Hi Conga (CONGA_HIGH)
# 63: Open Hi Conga (CONGA_HIGH_OPEN)
# 64: Low Conga (CONGA_LOW)
# 65: High Timbale (TIMBALE_HIGH)
# 66: Low Timbale (TIMBALE_LOW)
# 67: High Agogo (AGOGO_HIGH)
# 68: Low Agogo (AGOGO_LOW)
# 69: Cabasa (CABASA)
# 70: Maracas (SHAKER)
# 71: Short Whistle (WHISTLE_SHORT)
# 72: Long Whistle (WHISTLE_LONG)
# 73: Short Guiro (GUIRO_SHORT)
# 74: Long Guiro (GUIRO_LONG)
# 75: Claves (CLAVES)
# 76: Hi Wood Block (WOODBLOCK_HIGH)
# 77: Low Wood Block (WOODBLOCK_LOW)
# 78: Mute Cuica
# 79: Open Cuica
# 80: Mute Triangle (TRIANGLE_MUTE)
# 81: Open Triangle (TRIANGLE_OPEN)
