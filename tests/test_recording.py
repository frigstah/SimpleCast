import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from simplecast.recording import (
    RECORDING_BITRATE,
    Mp3FileWriter,
    next_recording_path,
)


class RecordingPathTests(unittest.TestCase):
    def test_timestamped_paths_do_not_overwrite_existing_recordings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            when = datetime(2026, 7, 28, 14, 5, 9)
            first = next_recording_path(folder, when)
            self.assertEqual(first.name, "SimpleCast-2026-07-28_14-05-09.mp3")
            first.touch()
            second = next_recording_path(folder, when)
            self.assertEqual(second.name, "SimpleCast-2026-07-28_14-05-09-2.mp3")


class Mp3FileWriterTests(unittest.TestCase):
    @patch("simplecast.recording.subprocess.Popen")
    @patch("simplecast.recording.get_ffmpeg_exe")
    def test_uses_320_kbps_and_selected_sample_rate(self, ffmpeg, popen) -> None:
        ffmpeg.return_value = "ffmpeg.exe"
        process = Mock()
        process.stdin = Mock()
        process.stdout = None
        process.stderr = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        popen.return_value = process

        destination = Path(r"C:\Recordings\show.mp3")
        writer = Mp3FileWriter(destination, 48000)
        writer.start(44100, 2)
        command = popen.call_args.args[0]

        self.assertIn(f"{RECORDING_BITRATE}k", command)
        output_rate_index = len(command) - 1 - command[::-1].index("-ar")
        self.assertEqual(command[output_rate_index + 1], "48000")
        self.assertEqual(command[-1], str(destination))

        writer.write(b"pcm")
        process.stdin.write.assert_called_once_with(b"pcm")
        writer.close()
        process.stdin.close.assert_called_once()
        process.wait.assert_called_once_with(timeout=3)

    @patch("simplecast.recording.subprocess.Popen")
    @patch("simplecast.recording.get_ffmpeg_exe")
    def test_uses_same_processing_filter_for_local_recording(
        self,
        ffmpeg,
        popen,
    ) -> None:
        ffmpeg.return_value = "ffmpeg.exe"
        process = Mock()
        process.stdin = Mock()
        process.stdout = None
        process.stderr = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        popen.return_value = process

        writer = Mp3FileWriter(Path("show.mp3"), 44100, "Mixed content")
        writer.start(48000, 2)
        command = popen.call_args.args[0]

        self.assertIn("-af", command)
        audio_filter = command[command.index("-af") + 1]
        self.assertIn("acompressor", audio_filter)
        self.assertIn("alimiter", audio_filter)


if __name__ == "__main__":
    unittest.main()
