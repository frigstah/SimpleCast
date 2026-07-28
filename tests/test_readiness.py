import unittest
from pathlib import Path
from unittest.mock import patch

from simplecast.audio import AudioDevice
from simplecast.models import AppConfig, ServerProfile
from simplecast.readiness import run_readiness_checks


class ReadinessTests(unittest.TestCase):
    @patch("simplecast.readiness._signature_check")
    @patch("simplecast.readiness._ffmpeg_capabilities")
    @patch("simplecast.readiness.platform.system", return_value="Windows")
    def test_flags_missing_station_password(
        self,
        _system,
        ffmpeg,
        signature,
    ) -> None:
        ffmpeg.return_value = (True, "Ready")
        signature.return_value = type(
            "Result",
            (),
            {
                "name": "Publisher signature",
                "status": "Warning",
                "detail": "Unsigned",
            },
        )()
        server = ServerProfile(host="radio.example")
        config = AppConfig(
            selected_server_id=server.id,
            enabled_server_ids=[server.id],
            servers=[server],
        )
        checks = run_readiness_checks(
            config,
            [AudioDevice(1, "Input", 2, 48000)],
            {},
            Path.cwd(),
            Path.cwd(),
        )
        station = next(
            check for check in checks if check.name == "Station configuration"
        )
        self.assertEqual(station.status, "Fail")
        self.assertIn("Missing password", station.detail)


if __name__ == "__main__":
    unittest.main()
