# What the Songs Found in kaiDAW

Writing two real songs through kaiDAW's protocol is the test its own `AGENTS.md` asks for.
No kaiDAW code changed during this work. These are the findings, most useful first, against
the build from 2026-09-11.

**Update, 2026-11-07.** kaiDAW's `song-gaps` branch addressed most of this, and puLang uses
all of it:

| Finding | Now |
|---|---|
| The crash | Found and fixed: an undo action held a Surge parameter after Tracktion freed the plugin on a one-second timer. A second crash, re-opening an open audio device, was found and fixed on the way. |
| Time signatures | `SetTempoMap` takes meters; Slow Orbit's ruler shows its 7/8 sections |
| Pitch bend and CC | `SetControllerPoints`; puLang's `Bend` pass writes scoops and falls, measured bending a note exactly two semitones |
| Plugin state | `RestorePluginState`; puLang loads Surge factory patches whole. Slow Orbit's Rhodes and pad use them. |
| Section markers | `SetMarkers`; every section occurrence is one |
| A master fader | `SetTrackState` on `master` takes volume and pan |
| `AddPlugin` after the fader | Inserts before it now |
| `metadata` | Accepted on the envelope |

Still open: samples and audio clips, sidechain routing, dry stems, unrepeatable bounces, and
the 127.0.0.1 binding (deliberate until kaiDAW has a security design). `/apply` still lists
no note ids, also deliberately: a clip of 2,000 notes would make a result bigger than its
command, and puLang matches new notes on content, exactly. After a Surge patch loads, kaiDAW's
projection shows the previous patch's values until reopen, because Surge does not tell the host.

## A crash to look at first

**The server has died twice with an access violation.** Exit code 5 from WSL is Windows'
`0xC0000005`, truncated. Both times a track holding Surge XT was being deleted shortly after a
render. It is intermittent: a deliberate attempt to reproduce it, loading Surge, rendering and
deleting the track, passed. puLang never deletes a track, so normal use does not hit it, but a
person pressing delete might.

## What would change the music

| Need | Today | Effect on the songs |
|---|---|---|
| **Time signatures** | `Tick::kPerBarFourFour` is a constant | Slow Orbit's 7/8 sections land on the right ticks, but the ruler and grid show 4/4 |
| **Pitch bend and CC lanes** | The note model has neither. Tracktion has them (`MidiList::addControllerEvent`). | No bends on the fusion lead or the future bass chop, which is much of what those lines are |
| **Plugin state** | `RestorePluginState` is in blueprint §6.5 and unimplemented. Surge reports zero programs. | Patches can only be built from parameters, which cannot reach Surge's modulation matrix, wavetables or stored patches. This is the largest limit on how good the songs can sound. |
| **Samples** | No audio clips, and the built-in Sampler cannot be loaded through the adapter | All drums are synthesised. Vocal chops are a synth standing in for one. |
| **Section markers** | No operation | `daw.marker` is compiled and dropped. Clips are named after their sections instead. |
| **A master fader** | `SetTrackState` refuses `master` | Headroom comes from a compressor's output gain |

Sidechain routing is also missing, but `Pump` covers the common case with a volume curve,
measured as a 13 dB duck.

## What would make it easier to drive

| | |
|---|---|
| `AddPlugin` appends after the fader and meter | An instrument added this way bypasses its own fader. Every client must follow it with `MovePlugin`. Inserting instruments first would remove the trap. |
| `/apply` does not return ids of created notes | A client has to read the whole `detail` projection and match on content |
| `metadata` on a command | DP-01 specifies it as a passthrough, and the wire rejects it as an unknown key |
| The server binds 127.0.0.1 | WSL has to hop through `curl.exe`, which failed to launch about twice in 80 calls, so puLang retries |
| Master bounce only | `pulang stems` solos each track instead, which also silences its sends, so stems are dry |
| A bounce is not repeatable | Known, Q-04. Two renders of one project differ slightly in spectrum. |

## What worked well

The design held up. `$alias` makes a whole song one transaction. `baseRevision` makes a recompile
safe against a person editing at the same moment. Note ids persist through save and reopen,
which is what the round trip rests on: a project reopened on a fresh server reconnected to its
source with zero differences. §3.10 put music above the protocol, and nothing in either song
needed that line moved.
