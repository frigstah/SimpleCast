import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from simplecast.encoder import get_ffmpeg_exe


class EncoderResolverTests(unittest.TestCase):
    def test_explicit_encoder_override_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "ffmpeg.exe"
            executable.touch()
            with patch.dict(
                os.environ,
                {"SIMPLECAST_FFMPEG_EXE": str(executable)},
            ):
                self.assertEqual(get_ffmpeg_exe(), str(executable))

    def test_invalid_encoder_override_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"SIMPLECAST_FFMPEG_EXE": "missing-ffmpeg.exe"},
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "does not point to a file",
            ):
                get_ffmpeg_exe()


if __name__ == "__main__":
    unittest.main()
