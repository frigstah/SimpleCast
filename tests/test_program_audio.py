import unittest

import numpy as np

from simplecast.audio import (
    AudioDevice,
    CaptureSelection,
    GainControl,
    ReverbControl,
    create_audio_source,
)
from simplecast.program_audio import (
    AudioProgram,
    MixedAudioSource,
    ProgramAudioSource,
    resolve_audio_program,
)


class ProgramAudioTests(unittest.TestCase):
    def test_program_label_includes_useful_window_title(self) -> None:
        program = AudioProgram(
            42,
            "chrome",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "SimpleCast Radio - Google Chrome",
        )
        self.assertEqual(
            program.label,
            "chrome — SimpleCast Radio - Google Chrome",
        )

    def test_program_is_resolved_after_its_pid_changes(self) -> None:
        original = AudioProgram(42, "Spotify", r"C:\Apps\Spotify.exe")
        restarted = AudioProgram(99, "Spotify", r"C:\Apps\Spotify.exe")
        self.assertEqual(
            resolve_audio_program(original, [restarted]),
            restarted,
        )

    def test_missing_program_reports_a_clear_error(self) -> None:
        original = AudioProgram(42, "KaraFun", r"C:\Apps\KaraFun.exe")
        with self.assertRaisesRegex(RuntimeError, "no longer running"):
            resolve_audio_program(original, [])

    def test_audio_source_factory_uses_program_loopback(self) -> None:
        program = AudioProgram(42, "Spotify", r"C:\Apps\Spotify.exe")
        source = create_audio_source(program, GainControl(125))
        self.assertIsInstance(source, ProgramAudioSource)
        self.assertEqual(source.sample_rate, 44100)
        self.assertEqual(source.channels, 2)

    def test_audio_source_factory_builds_device_and_program_mixer(self) -> None:
        device = AudioDevice(1, "Microphone", 1, 48000)
        program = AudioProgram(42, "KaraFun", r"C:\Apps\KaraFun.exe")
        device_gain = GainControl(80)
        program_gain = GainControl(120)
        reverb = ReverbControl(True, 40)
        source = create_audio_source(
            CaptureSelection(device, program),
            device_gain,
            program_gain=program_gain,
            reverb=reverb,
        )
        self.assertIsInstance(source, MixedAudioSource)
        self.assertIs(source.device_gain, device_gain)
        self.assertIs(source.program_gain, program_gain)
        self.assertIs(source.reverb, reverb)
        self.assertEqual(source.channels, 2)

    def test_mixer_adds_device_and_program_audio_and_clips_safely(self) -> None:
        device = np.array([[1000], [30000]], dtype="<i2")
        program = np.array(
            [[2000, -500], [10000, 10000]],
            dtype="<i2",
        )
        mixed = MixedAudioSource.mix_pcm_blocks(
            device.tobytes(),
            1,
            program.tobytes(),
        )
        samples = np.frombuffer(mixed, dtype="<i2").reshape(-1, 2)
        self.assertTrue(np.allclose(samples[0], [2999, 499], atol=1))
        self.assertEqual(samples[1, 0], 32767)
        self.assertEqual(samples[1, 1], 32767)


if __name__ == "__main__":
    unittest.main()
