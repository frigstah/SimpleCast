import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from simplecast.processing import (
    PROCESSING_PRESETS,
    filter_arguments,
    process_test_file,
)


class ProcessingPresetTests(unittest.TestCase):
    def test_all_active_presets_include_peak_limiter(self) -> None:
        for name, preset in PROCESSING_PRESETS.items():
            if name != "Off / Original":
                self.assertIn("alimiter", preset.ffmpeg_filter)

    def test_off_preset_does_not_add_ffmpeg_filter(self) -> None:
        self.assertEqual(filter_arguments("Off / Original"), [])

    def test_ffmpeg_can_render_each_processed_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "original.wav"
            sample_rate = 44100
            samples = [
                int(10000 * math.sin(2 * math.pi * 440 * index / sample_rate))
                for index in range(sample_rate // 10)
            ]
            with wave.open(str(source), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(sample_rate)
                output.writeframes(
                    b"".join(struct.pack("<h", sample) for sample in samples)
                )

            for name in PROCESSING_PRESETS:
                destination = root / f"{name.replace('/', '-')}.wav"
                process_test_file(source, destination, name)
                self.assertGreater(destination.stat().st_size, 44)


if __name__ == "__main__":
    unittest.main()
