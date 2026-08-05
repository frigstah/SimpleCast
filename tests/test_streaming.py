import queue
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import sounddevice as sd
import numpy as np

from simplecast.audio import (
    AudioDevice,
    AudioEngine,
    BroadcastAudioSource,
    CaptureOption,
    GainControl,
    _start_input_stream,
)
from simplecast.models import ServerProfile
from simplecast.streaming import (
    BroadcastState,
    MultiStreamEngine,
    QUALITY_PRESETS,
    StreamEngine,
)


class StreamCommandTests(unittest.TestCase):
    @patch("simplecast.streaming.subprocess.Popen")
    @patch("simplecast.streaming.get_ffmpeg_exe")
    def test_icecast_uses_mp3_stdout_encoder(self, ffmpeg, popen) -> None:
        ffmpeg.return_value = "ffmpeg.exe"
        popen.return_value = object()
        engine = StreamEngine(lambda *_: None, lambda *_: None)
        source = BroadcastAudioSource(
            AudioDevice(index=1, name="Input", channels=2, sample_rate=48000)
        )
        server = ServerProfile(
            host="radio.example",
            port=8443,
            mount="/live",
            username="source",
            use_tls=True,
        )
        engine._start_ffmpeg(source, server, "secret word", "SL MAX unsafe")
        command = popen.call_args.args[0]
        self.assertIn("libmp3lame", command)
        output_rate_index = len(command) - 1 - command[::-1].index("-ar")
        self.assertEqual(command[output_rate_index + 1], "44100")
        self.assertEqual(command[-1], "pipe:1")
        self.assertNotIn("secret word", " ".join(command))
        self.assertEqual(popen.call_args.kwargs["stdout"], -1)

    def test_stream_engine_accepts_device_reresolver(self) -> None:
        replacement = AudioDevice(21, "Input", 2, 44100)
        resolver = Mock(return_value=replacement)
        engine = StreamEngine(
            lambda *_: None,
            lambda *_: None,
            device_resolver=resolver,
        )
        original = AudioDevice(46, "Input", 2, 48000)
        self.assertIs(engine.device_resolver(original), replacement)
        resolver.assert_called_once_with(original)

    @patch("simplecast.streaming.subprocess.Popen")
    @patch("simplecast.streaming.get_ffmpeg_exe")
    def test_shoutcast_uses_mp3_stdout_encoder(self, ffmpeg, popen) -> None:
        ffmpeg.return_value = "ffmpeg.exe"
        popen.return_value = object()
        engine = StreamEngine(lambda *_: None, lambda *_: None)
        source = BroadcastAudioSource(
            AudioDevice(index=1, name="Input", channels=2, sample_rate=48000)
        )
        server = ServerProfile(server_type="shoutcast2", host="radio.example")
        engine._start_ffmpeg(source, server, "secret", "SL MAX unsafe", 48000)
        command = popen.call_args.args[0]
        self.assertEqual(command[-1], "pipe:1")
        output_rate_index = len(command) - 1 - command[::-1].index("-ar")
        self.assertEqual(command[output_rate_index + 1], "48000")
        self.assertNotIn("icecast://", " ".join(command))
        self.assertEqual(popen.call_args.kwargs["stdout"], -1)

    @patch("simplecast.streaming.subprocess.Popen")
    @patch("simplecast.streaming.get_ffmpeg_exe")
    def test_processing_preset_adds_live_audio_filter(
        self,
        ffmpeg,
        popen,
    ) -> None:
        ffmpeg.return_value = "ffmpeg.exe"
        popen.return_value = object()
        engine = StreamEngine(lambda *_: None, lambda *_: None)
        source = BroadcastAudioSource(
            AudioDevice(index=1, name="Input", channels=2, sample_rate=48000)
        )
        server = ServerProfile(host="radio.example", mount="/live")

        engine._start_ffmpeg(
            source,
            server,
            "secret",
            "SL Standard",
            44100,
            "Voice",
        )

        command = popen.call_args.args[0]
        self.assertIn("-af", command)
        audio_filter = command[command.index("-af") + 1]
        self.assertIn("acompressor", audio_filter)
        self.assertIn("alimiter", audio_filter)


class AudioShutdownTests(unittest.TestCase):
    def test_meter_uses_abort_instead_of_blocking_stop(self) -> None:
        class FakeStream:
            def __init__(self) -> None:
                self.aborted = False
                self.closed = False

            def abort(self) -> None:
                self.aborted = True

            def close(self) -> None:
                self.closed = True

            def stop(self) -> None:
                raise AssertionError("stop() can block in a Windows USB driver")

        engine = AudioEngine()
        fake = FakeStream()
        engine._meter_stream = fake
        engine.stop_meter()
        self.assertTrue(fake.aborted)
        self.assertTrue(fake.closed)
        self.assertIsNone(engine._meter_stream)

    @patch("simplecast.audio.time.sleep")
    @patch("simplecast.audio.sd.InputStream")
    def test_capture_falls_back_when_wasapi_rejects_device(
        self,
        input_stream,
        _sleep,
    ) -> None:
        class FakeStream:
            def __init__(self, fails: bool) -> None:
                self.fails = fails

            def start(self) -> None:
                if self.fails:
                    raise sd.PortAudioError("WASAPI device error")

            def close(self) -> None:
                pass

        input_stream.side_effect = lambda **kwargs: FakeStream(kwargs["device"] == 46)
        device = AudioDevice(
            index=46,
            name="IN 1-2",
            channels=2,
            sample_rate=48000,
            fallbacks=(CaptureOption(21, 2, 44100, "Windows DirectSound"),),
        )
        stream, option = _start_input_stream(device, lambda *_: None)
        self.assertIsInstance(stream, FakeStream)
        self.assertEqual(option.index, 21)
        self.assertEqual(option.sample_rate, 44100)

    @patch("simplecast.audio.sd.InputStream")
    def test_explicit_wasapi_uses_shared_mode_and_automatic_blocksize(
        self,
        input_stream,
    ) -> None:
        class FakeStream:
            def start(self) -> None:
                pass

        input_stream.return_value = FakeStream()
        device = AudioDevice(46, "IN 1-2", 2, 48000)
        _stream, option = _start_input_stream(
            device,
            lambda *_: None,
            "Windows WASAPI (shared)",
        )
        arguments = input_stream.call_args.kwargs
        self.assertEqual(option.api_name, "Windows WASAPI")
        self.assertEqual(arguments["blocksize"], 0)
        self.assertIsInstance(arguments["extra_settings"], sd.WasapiSettings)

    @patch("simplecast.audio.time.sleep")
    @patch("simplecast.audio.sd.InputStream")
    def test_explicit_wasapi_does_not_silently_fallback(
        self,
        input_stream,
        _sleep,
    ) -> None:
        input_stream.side_effect = sd.PortAudioError("WASAPI failed")
        device = AudioDevice(
            46,
            "IN 1-2",
            2,
            48000,
            fallbacks=(CaptureOption(21, 2, 44100, "Windows DirectSound"),),
        )
        with self.assertRaises(sd.PortAudioError):
            _start_input_stream(
                device,
                lambda *_: None,
                "Windows WASAPI (shared)",
            )
        self.assertEqual(input_stream.call_count, 2)
        self.assertTrue(
            all(
                call.kwargs["device"] == 46
                for call in input_stream.call_args_list
            )
        )

    @patch("simplecast.audio.time.monotonic")
    @patch("simplecast.audio.create_audio_source")
    def test_sound_check_emits_live_meter_levels(
        self,
        create_source,
        monotonic,
    ) -> None:
        source = SimpleNamespace(
            blocks=queue.Queue(),
            levels=(0.2, 0.4),
            peak_level=0.6,
            channels=2,
            sample_rate=48000,
            active_api="Mixed audio",
            failure="",
            start=Mock(),
            stop=Mock(),
        )
        source.blocks.put(
            np.array([[1000, -1000]], dtype="<i2").tobytes()
        )
        create_source.return_value = source
        monotonic.side_effect = [0.0, 0.0, 2.0]
        levels: list[tuple[float, float, float]] = []
        engine = AudioEngine()

        with tempfile.TemporaryDirectory() as folder:
            engine.record_test(
                object(),
                Path(folder) / "test.wav",
                seconds=1,
                level_callback=lambda left, right, peak: levels.append(
                    (left, right, peak)
                ),
            )

        self.assertEqual(levels, [(0.2, 0.4, 0.6)])
        source.stop.assert_called_once_with()


class GainAndQualityTests(unittest.TestCase):
    def test_gain_is_applied_and_clipped(self) -> None:
        gain = GainControl(150)
        adjusted = gain.apply(np.array([[0.25, 0.8]], dtype=np.float32))
        np.testing.assert_allclose(adjusted, [[0.375, 1.0]])

    def test_gain_can_change_while_running(self) -> None:
        gain = GainControl(100)
        self.assertEqual(gain.multiplier, 1.0)
        gain.set_percent(175)
        self.assertEqual(gain.multiplier, 1.75)

    def test_requested_quality_presets(self) -> None:
        self.assertEqual(QUALITY_PRESETS["SL Standard"].bitrate, 128)
        self.assertEqual(QUALITY_PRESETS["SL MAX unsafe"].bitrate, 192)
        self.assertEqual(QUALITY_PRESETS["Recording"].bitrate, 320)
        self.assertTrue(
            all(preset.channels is None for preset in QUALITY_PRESETS.values())
        )


class MultiStreamStatusTests(unittest.TestCase):
    def test_one_failed_server_does_not_take_online_server_off_air(self) -> None:
        summaries: list[tuple[BroadcastState, str]] = []
        individual: list[tuple[str, BroadcastState, str]] = []
        engine = MultiStreamEngine(
            lambda state, detail: summaries.append((state, detail)),
            lambda server_id, state, detail: individual.append(
                (server_id, state, detail)
            ),
            lambda *_: None,
        )
        engine._statuses = {
            "one": (BroadcastState.CONNECTING, ""),
            "two": (BroadcastState.CONNECTING, ""),
        }

        engine._on_server_state("one", BroadcastState.ON_AIR, "On air: One")
        engine._on_server_state(
            "two",
            BroadcastState.RECONNECTING,
            "Two: connection lost",
        )

        self.assertEqual(summaries[-1][0], BroadcastState.ON_AIR)
        self.assertIn("1 of 2 servers online", summaries[-1][1])
        self.assertIn("1 reconnecting", summaries[-1][1])
        self.assertEqual(individual[-1][0], "two")


if __name__ == "__main__":
    unittest.main()
