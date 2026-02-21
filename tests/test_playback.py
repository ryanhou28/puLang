"""
Tests for the pypulang playback system.

Tests cover:
- Instrument classes (Synth, InstrumentBank)
- Playback protocols
- Event realization
- Backend availability detection
"""

import pytest
from fractions import Fraction

from pypulang import piece, I, IV, vi, V, Role, root_quarters
from pypulang.midi import realize_to_events
from pypulang.playback.instruments import Synth, InstrumentBank, SynthBass, SynthPad, SynthLead
from pypulang.playback.protocols import PlaybackBackend, PlaybackHandle
from pypulang.playback.config import get_available_backends


# =============================================================================
# Synth Tests
# =============================================================================


class TestSynth:
    """Tests for the Synth instrument class."""

    def test_default_synth_creation(self):
        """Test creating a synth with default parameters."""
        synth = Synth()
        assert synth.waveform == "sine"
        assert synth.attack == 0.01
        assert synth.decay == 0.1
        assert synth.sustain == 0.7
        assert synth.release == 0.2
        assert synth.filter_type is None

    def test_synth_with_custom_waveform(self):
        """Test creating synth with different waveforms."""
        for waveform in ["sine", "square", "saw", "triangle"]:
            synth = Synth(waveform=waveform)
            assert synth.waveform == waveform

    def test_synth_invalid_waveform_raises(self):
        """Test that invalid waveform raises ValueError."""
        with pytest.raises(ValueError, match="Invalid waveform"):
            Synth(waveform="invalid")

    def test_synth_with_filter(self):
        """Test synth with filter settings."""
        synth = Synth(filter_type="lowpass", cutoff=500)
        assert synth.filter_type == "lowpass"
        assert synth.cutoff == 500

    def test_synth_invalid_filter_raises(self):
        """Test that invalid filter type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid filter_type"):
            Synth(filter_type="bandpass")

    def test_synth_invalid_sustain_raises(self):
        """Test that sustain outside 0-1 raises ValueError."""
        with pytest.raises(ValueError, match="Sustain must be 0-1"):
            Synth(sustain=1.5)

    def test_synth_adsr_parameters(self):
        """Test custom ADSR parameters."""
        synth = Synth(attack=0.05, decay=0.2, sustain=0.5, release=0.3)
        assert synth.attack == 0.05
        assert synth.decay == 0.2
        assert synth.sustain == 0.5
        assert synth.release == 0.3


class TestSynthPresets:
    """Tests for synth preset functions."""

    def test_synth_bass_preset(self):
        """Test SynthBass preset."""
        synth = SynthBass()
        assert synth.waveform == "saw"
        assert synth.filter_type == "lowpass"
        assert synth.cutoff == 400

    def test_synth_pad_preset(self):
        """Test SynthPad preset."""
        synth = SynthPad()
        assert synth.waveform == "triangle"
        assert synth.attack > 0.1  # Slow attack

    def test_synth_lead_preset(self):
        """Test SynthLead preset."""
        synth = SynthLead()
        assert synth.waveform == "square"
        assert synth.attack < 0.05  # Fast attack


# =============================================================================
# Synth Rendering Tests
# =============================================================================


class TestSynthRender:
    """Tests for Synth audio rendering."""

    @pytest.fixture
    def numpy_available(self):
        """Check if numpy is available."""
        try:
            import numpy
            return True
        except ImportError:
            pytest.skip("numpy not installed")

    def test_synth_render_returns_array(self, numpy_available):
        """Test that render returns a numpy array."""
        import numpy as np

        synth = Synth()
        audio = synth.render(pitch=60, duration=0.5, velocity=100, sample_rate=44100)
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32

    def test_synth_render_correct_length(self, numpy_available):
        """Test that rendered audio has correct length."""
        synth = Synth(release=0.2)
        audio = synth.render(pitch=60, duration=0.5, velocity=100, sample_rate=44100)
        # Duration (0.5) + release (0.2) = 0.7 seconds
        expected_samples = int(0.7 * 44100)
        assert len(audio) == expected_samples

    def test_synth_render_normalized(self, numpy_available):
        """Test that rendered audio is normalized."""
        import numpy as np

        synth = Synth()
        audio = synth.render(pitch=60, duration=0.5, velocity=127, sample_rate=44100)
        assert np.max(np.abs(audio)) <= 1.0

    def test_synth_render_velocity_affects_amplitude(self, numpy_available):
        """Test that velocity affects amplitude."""
        import numpy as np

        synth = Synth()
        audio_loud = synth.render(pitch=60, duration=0.5, velocity=127, sample_rate=44100)
        audio_quiet = synth.render(pitch=60, duration=0.5, velocity=32, sample_rate=44100)

        # Louder should have higher max amplitude
        assert np.max(np.abs(audio_loud)) > np.max(np.abs(audio_quiet))

    def test_synth_render_different_pitches(self, numpy_available):
        """Test rendering different pitches."""
        synth = Synth()
        # Should not raise for valid MIDI pitches
        for pitch in [24, 60, 96, 108]:
            audio = synth.render(pitch=pitch, duration=0.1, velocity=100, sample_rate=44100)
            assert len(audio) > 0


# =============================================================================
# InstrumentBank Tests
# =============================================================================


class TestInstrumentBank:
    """Tests for InstrumentBank class."""

    def test_empty_bank(self):
        """Test creating empty instrument bank."""
        bank = InstrumentBank()
        # Should return default instruments
        instrument = bank.get_instrument("bass", "bass")
        assert isinstance(instrument, Synth)

    def test_bank_with_role_mapping(self):
        """Test bank with role-based mapping."""
        bass_synth = Synth(waveform="saw")
        bank = InstrumentBank({Role.BASS: bass_synth})

        instrument = bank.get_instrument("any_track", "bass")
        assert instrument is bass_synth

    def test_bank_with_name_mapping(self):
        """Test bank with track name mapping."""
        lead_synth = Synth(waveform="square")
        bank = InstrumentBank({"lead": lead_synth})

        instrument = bank.get_instrument("lead", None)
        assert instrument is lead_synth

    def test_bank_name_takes_precedence(self):
        """Test that track name takes precedence over role."""
        role_synth = Synth(waveform="sine")
        name_synth = Synth(waveform="square")

        bank = InstrumentBank({
            Role.BASS: role_synth,
            "bass": name_synth,
        })

        # Name should take precedence
        instrument = bank.get_instrument("bass", "bass")
        assert instrument is name_synth

    def test_bank_default_for_unknown_role(self):
        """Test that unknown roles get default instrument."""
        bank = InstrumentBank()
        instrument = bank.get_instrument("unknown_track", None)
        assert isinstance(instrument, Synth)
        assert instrument.waveform == "sine"  # Default

    def test_bank_default_instruments_per_role(self):
        """Test that different roles get different defaults."""
        bank = InstrumentBank()

        bass_inst = bank.get_instrument("t1", "bass")
        melody_inst = bank.get_instrument("t2", "melody")
        harmony_inst = bank.get_instrument("t3", "harmony")

        # Different roles should have different default configs
        assert bass_inst.waveform == "saw"
        assert melody_inst.waveform == "square"
        assert harmony_inst.waveform == "triangle"

    def test_bank_set_instrument(self):
        """Test setting instrument after creation."""
        bank = InstrumentBank()
        new_synth = Synth(waveform="triangle")

        bank.set_instrument("lead", new_synth)

        instrument = bank.get_instrument("lead", None)
        assert instrument is new_synth

    def test_bank_set_instrument_chaining(self):
        """Test that set_instrument returns self for chaining."""
        bank = InstrumentBank()
        result = bank.set_instrument("lead", Synth())
        assert result is bank


# =============================================================================
# Event Realization Tests
# =============================================================================


class TestRealizeToEvents:
    """Tests for realize_to_events function."""

    def test_basic_realization(self):
        """Test basic piece realization to events."""
        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters)

        ir = p.to_ir()
        events, tempo = realize_to_events(ir)

        assert tempo == 120
        assert len(events) > 0

        # Check event format
        for event in events:
            pitch, start, duration, velocity, track_name, role = event
            assert isinstance(pitch, int)
            assert isinstance(start, float)
            assert isinstance(duration, float)
            assert isinstance(velocity, int)
            assert track_name == "bass"
            assert role == "bass"

    def test_realization_section_filter(self):
        """Test realizing only a specific section."""
        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV)
            verse.track("bass", role=Role.BASS).pattern(root_quarters)

            chorus = p.section("chorus", bars=4)
            chorus.harmony(V, I)
            chorus.track("bass", role=Role.BASS).pattern(root_quarters)

        ir = p.to_ir()

        # Full piece
        all_events, _ = realize_to_events(ir)

        # Just verse
        verse_events, _ = realize_to_events(ir, section="verse")

        # Just chorus
        chorus_events, _ = realize_to_events(ir, section="chorus")

        # Verse + chorus should equal all (roughly, depending on timing)
        assert len(verse_events) < len(all_events)
        assert len(chorus_events) < len(all_events)

    def test_realization_from_bar(self):
        """Test starting from a specific bar."""
        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I, IV, vi, V)
            verse.track("bass", role=Role.BASS).pattern(root_quarters)

        ir = p.to_ir()

        # From bar 1 (all events)
        all_events, _ = realize_to_events(ir, from_bar=1)

        # From bar 3 (should have fewer events)
        later_events, _ = realize_to_events(ir, from_bar=3)

        assert len(later_events) < len(all_events)

    def test_realization_unknown_section_raises(self):
        """Test that unknown section raises ValueError."""
        with piece(tempo=120, key="C major") as p:
            verse = p.section("verse", bars=4)
            verse.harmony(I)

        ir = p.to_ir()

        with pytest.raises(ValueError, match="Unknown section"):
            realize_to_events(ir, section="unknown")


# =============================================================================
# Backend Availability Tests
# =============================================================================


class TestBackendAvailability:
    """Tests for backend availability detection."""

    def test_get_available_backends_returns_list(self):
        """Test that get_available_backends returns a list."""
        backends = get_available_backends()
        assert isinstance(backends, list)

    def test_available_backends_have_correct_interface(self):
        """Test that available backends implement the protocol."""
        backends = get_available_backends()

        for backend in backends:
            # Check required methods exist
            assert hasattr(backend, 'play')
            assert hasattr(backend, 'is_available')
            assert hasattr(backend, 'name')

            # is_available should return True (since it's in available list)
            assert backend.is_available() is True

            # name should return a string
            assert isinstance(backend.name(), str)


# =============================================================================
# DSL Playback Integration Tests
# =============================================================================


class TestDSLPlaybackIntegration:
    """Tests for playback integration in DSL."""

    def test_piece_has_play_method(self):
        """Test that PieceBuilder has play method."""
        with piece(tempo=120, key="C major") as p:
            pass

        assert hasattr(p, 'play')
        assert callable(p.play)

    def test_piece_has_loop_method(self):
        """Test that PieceBuilder has loop method."""
        with piece(tempo=120, key="C major") as p:
            pass

        assert hasattr(p, 'loop')
        assert callable(p.loop)

    def test_piece_has_connect_method(self):
        """Test that PieceBuilder has connect method."""
        with piece(tempo=120, key="C major") as p:
            pass

        assert hasattr(p, 'connect')
        assert callable(p.connect)

    def test_piece_has_list_ports_method(self):
        """Test that PieceBuilder has list_ports method."""
        with piece(tempo=120, key="C major") as p:
            pass

        assert hasattr(p, 'list_ports')
        assert callable(p.list_ports)


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestProtocolCompliance:
    """Tests for protocol compliance."""

    def test_playback_handle_protocol(self):
        """Test that PlaybackHandle is a proper protocol."""
        # Should be able to check isinstance with runtime_checkable protocols
        from pypulang.playback.protocols import PlaybackHandle

        # The protocol should define these methods
        assert hasattr(PlaybackHandle, 'stop')
        assert hasattr(PlaybackHandle, 'pause')
        assert hasattr(PlaybackHandle, 'resume')
        assert hasattr(PlaybackHandle, 'is_playing')
        assert hasattr(PlaybackHandle, 'is_paused')
        assert hasattr(PlaybackHandle, 'wait')
        assert hasattr(PlaybackHandle, 'get_position_seconds')
        assert hasattr(PlaybackHandle, 'get_position_beats')

    def test_playback_backend_protocol(self):
        """Test that PlaybackBackend is a proper protocol."""
        from pypulang.playback.protocols import PlaybackBackend

        # The protocol should define these methods
        assert hasattr(PlaybackBackend, 'play')
        assert hasattr(PlaybackBackend, 'is_available')
        assert hasattr(PlaybackBackend, 'name')


# =============================================================================
# Hot Reload Tests
# =============================================================================


class TestFileWatcher:
    """Tests for FileWatcher class."""

    def test_file_watcher_creation(self, tmp_path):
        """Test creating a file watcher."""
        from pypulang.playback.watcher import FileWatcher

        test_file = tmp_path / "test.py"
        test_file.write_text("# test")

        callback_called = []
        def callback():
            callback_called.append(True)

        watcher = FileWatcher(test_file, callback, poll_interval=0.1)
        assert watcher._file_path == test_file.resolve()

    def test_file_watcher_detects_change(self, tmp_path):
        """Test that watcher detects file changes."""
        import time
        from pypulang.playback.watcher import FileWatcher

        test_file = tmp_path / "test.py"
        test_file.write_text("# version 1")

        callback_called = []
        def callback():
            callback_called.append(True)

        watcher = FileWatcher(test_file, callback, poll_interval=0.1)
        watcher.start()

        try:
            # Modify the file
            time.sleep(0.2)
            test_file.write_text("# version 2")
            time.sleep(0.3)

            # Callback should have been called
            assert len(callback_called) >= 1
        finally:
            watcher.stop()

    def test_file_watcher_stop(self, tmp_path):
        """Test stopping the watcher."""
        from pypulang.playback.watcher import FileWatcher

        test_file = tmp_path / "test.py"
        test_file.write_text("# test")

        watcher = FileWatcher(test_file, lambda: None, poll_interval=0.1)
        watcher.start()
        watcher.stop()

        assert not watcher._running


class TestWatchHandle:
    """Tests for WatchHandle class."""

    def test_watch_handle_creation(self, tmp_path):
        """Test creating a watch handle."""
        from pypulang.playback.watcher import FileWatcher, WatchHandle

        test_file = tmp_path / "test.py"
        test_file.write_text("# test")

        watcher = FileWatcher(test_file, lambda: None)
        handle = WatchHandle(watcher, None, test_file)

        assert handle.file_path == test_file
        assert handle.is_watching()

    def test_watch_handle_stop(self, tmp_path):
        """Test stopping a watch handle."""
        from pypulang.playback.watcher import FileWatcher, WatchHandle

        test_file = tmp_path / "test.py"
        test_file.write_text("# test")

        watcher = FileWatcher(test_file, lambda: None)
        watcher.start()

        handle = WatchHandle(watcher, None, test_file)
        handle.stop()

        assert not handle.is_watching()
        assert not watcher._running


class TestGetCallerFile:
    """Tests for get_caller_file function."""

    def test_get_caller_file(self):
        """Test getting caller file from test module."""
        from pypulang.playback.watcher import get_caller_file

        # When called from a test, should return the test file path
        caller_file = get_caller_file()
        assert caller_file is not None
        assert caller_file.suffix == ".py"


class TestHotReloadDSL:
    """Tests for hot reload integration with DSL."""

    def test_piece_has_watch_method(self):
        """Test that PieceBuilder has watch method."""
        with piece(tempo=120, key="C major") as p:
            pass

        assert hasattr(p, 'watch')
        assert callable(p.watch)

    def test_watch_piece_function_exists(self):
        """Test that watch_piece function is exported."""
        from pypulang.playback import watch_piece

        assert callable(watch_piece)

    def test_file_watcher_exported(self):
        """Test that FileWatcher is exported."""
        from pypulang.playback import FileWatcher

        assert FileWatcher is not None

    def test_watch_handle_exported(self):
        """Test that WatchHandle is exported."""
        from pypulang.playback import WatchHandle

        assert WatchHandle is not None


class TestPositionTracking:
    """Tests for playback position tracking."""

    def test_base_handle_position_defaults(self):
        """Test that BasePlaybackHandle has default position methods."""
        from pypulang.playback.protocols import BasePlaybackHandle

        assert hasattr(BasePlaybackHandle, 'get_position_seconds')
        assert hasattr(BasePlaybackHandle, 'get_position_beats')

    @pytest.fixture
    def numpy_available(self):
        """Check if numpy is available."""
        try:
            import numpy
            return True
        except ImportError:
            pytest.skip("numpy not installed")

    def test_builtin_synth_handle_position(self, numpy_available):
        """Test BuiltinSynthHandle position tracking."""
        import numpy as np
        from pypulang.playback.builtin_synth import BuiltinSynthHandle, SOUNDDEVICE_AVAILABLE

        if not SOUNDDEVICE_AVAILABLE:
            pytest.skip("sounddevice not installed")

        # Create a handle with some audio data
        audio = np.zeros(44100, dtype=np.float32)  # 1 second at 44100 Hz
        handle = BuiltinSynthHandle(audio, sample_rate=44100)

        # Position should start at 0
        assert handle.get_position_seconds() == 0.0
        assert handle.get_position_beats(120) == 0.0

        # Simulate some playback progress
        handle._position = 22050  # Half a second
        assert handle.get_position_seconds() == 0.5
        assert handle.get_position_beats(120) == 1.0  # 120 BPM = 2 beats/sec
