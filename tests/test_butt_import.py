from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simplecast.butt_import import (
    ButtImportError,
    ButtServer,
    exclude_existing_butt_servers,
    load_butt_server_export,
)
from simplecast.models import ServerProfile


class ButtImportTests(unittest.TestCase):
    @staticmethod
    def _write(directory: str, content: str) -> Path:
        path = Path(directory) / "BUTT export"
        path.write_text(content, encoding="utf-8")
        return path

    def test_imports_only_named_server_sections(self) -> None:
        content = """\
#This is a configuration file for butt (broadcast using this tool)

[main]
server = Ice station
srv_ent = Shout station;Ice station
num_of_srv = 2

[audio]
device = 9
bitrate = 64

[Shout station]
address = shout.example
port = 8000
password = shout-secret
type = 0
tls = 0
mount = (none)
usr = source

[Ice station]
address = ice.example
port = 8443
password = ice-secret
type = 1
tls = 1
mount = studio
usr = dj

[Not a server]
address = ignored.example
port = 9000
password = ignored-secret
type = 0
"""
        with tempfile.TemporaryDirectory() as directory:
            result = load_butt_server_export(self._write(directory, content))

        self.assertEqual(len(result.servers), 2)
        shout, ice = result.servers
        self.assertEqual(shout.profile.server_type, "shoutcast1")
        self.assertEqual(shout.profile.host, "shout.example")
        self.assertEqual(shout.profile.mount, "")
        self.assertEqual(shout.password, "shout-secret")
        self.assertTrue(shout.profile.shoutcast_port_plus_one)
        self.assertEqual(ice.profile.server_type, "icecast2")
        self.assertEqual(ice.profile.mount, "/studio")
        self.assertEqual(ice.profile.username, "dj")
        self.assertEqual(ice.password, "ice-secret")
        self.assertTrue(ice.profile.use_tls)
        self.assertEqual(result.selected_server_name, "Ice station")
        self.assertEqual(result.skipped, ())

    def test_preserves_shoutcast_compatibility_password_verbatim(self) -> None:
        content = """\
[main]
srv_ent = SC2
[SC2]
address = radio.example
port = 8000
password = MyUser:MyPassword:#3
type = 0
tls = 0
mount = (none)
"""
        with tempfile.TemporaryDirectory() as directory:
            result = load_butt_server_export(self._write(directory, content))

        imported = result.servers[0]
        self.assertEqual(imported.profile.server_type, "shoutcast1")
        self.assertEqual(imported.password, "MyUser:MyPassword:#3")

    def test_skips_missing_and_unsupported_server_sections(self) -> None:
        content = """\
[main]
srv_ent = Missing;WebRTC;Broken ice
[WebRTC]
address = whip.example
port = 443
password = token
type = 2
[Broken ice]
address = ice.example
port = 8000
password = secret
type = 1
mount = (none)
"""
        with tempfile.TemporaryDirectory() as directory:
            result = load_butt_server_export(self._write(directory, content))

        self.assertEqual(result.servers, ())
        self.assertEqual(len(result.skipped), 3)

    def test_rejects_non_butt_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, "[audio]\ndevice = 1\n")
            with self.assertRaises(ButtImportError):
                load_butt_server_export(path)

    def test_exact_duplicates_are_not_added_twice(self) -> None:
        saved = ButtServer(
            ServerProfile(
                name="Saved",
                server_type="shoutcast1",
                host="RADIO.example",
                port=8000,
            ).normalized(),
            "secret",
        )
        exact_copy = ButtServer(
            ServerProfile(
                name="saved",
                server_type="shoutcast1",
                host="radio.EXAMPLE",
                port=8000,
            ).normalized(),
            "secret",
        )
        different_password = ButtServer(
            ServerProfile(
                name="Saved",
                server_type="shoutcast1",
                host="radio.example",
                port=8000,
            ).normalized(),
            "other-secret",
        )

        additions, duplicates = exclude_existing_butt_servers(
            [exact_copy, different_password, different_password],
            [saved],
        )

        self.assertEqual(duplicates, 2)
        self.assertEqual(additions, (different_password,))


if __name__ == "__main__":
    unittest.main()
