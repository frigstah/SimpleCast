import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from simplecast.metadata import (
    MetadataDeliveryEngine,
    MetadataFileWatcher,
    format_metadata_text,
    send_now_playing,
)
from simplecast.models import ServerProfile


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class MetadataTests(unittest.TestCase):
    @patch("simplecast.metadata.urllib.request.urlopen", return_value=FakeResponse())
    def test_shoutcast_metadata_uses_sid_and_source_password(self, urlopen) -> None:
        server = ServerProfile(
            server_type="shoutcast2",
            host="radio.example",
            port=8000,
            stream_id=3,
        )
        send_now_playing(server, "secret", "Artist - Title")
        request = urlopen.call_args.args[0]
        parsed = urlparse(request.full_url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.path, "/admin.cgi")
        self.assertEqual(query["sid"], ["3"])
        self.assertEqual(query["pass"], ["secret"])
        self.assertEqual(query["song"], ["Artist - Title"])

    def test_formats_two_line_artist_and_title(self) -> None:
        self.assertEqual(
            format_metadata_text(
                "\ufeff Artist Name \n Song Title \nIgnored",
                "Artist - Title (first two lines)",
            ),
            "Artist Name - Song Title",
        )
        self.assertEqual(
            format_metadata_text("Artist - Title\n", "As written"),
            "Artist - Title",
        )

    def test_file_watcher_ignores_empty_and_duplicate_titles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "now-playing.txt"
            titles: list[str] = []
            updated = threading.Event()

            def receive(title: str) -> None:
                titles.append(title)
                updated.set()

            watcher = MetadataFileWatcher(
                receive,
                lambda _status: None,
                poll_seconds=0.02,
            )
            path.write_text("Artist - First", encoding="utf-8")
            watcher.start(path, "As written")
            self.assertTrue(updated.wait(1))
            updated.clear()
            path.write_text("Artist - First\n", encoding="utf-8")
            time.sleep(0.08)
            self.assertFalse(updated.is_set())
            path.write_text("Artist - Second", encoding="utf-8")
            self.assertTrue(updated.wait(1))
            watcher.stop()
            self.assertEqual(titles, ["Artist - First", "Artist - Second"])

    @patch("simplecast.metadata.send_now_playing")
    def test_delivery_retries_only_failed_servers(self, send) -> None:
        first = ServerProfile(name="One")
        second = ServerProfile(name="Two")
        attempts = {first.id: 0, second.id: 0}

        def deliver(server, _password, _song):
            attempts[server.id] += 1
            if server.id == second.id and attempts[server.id] == 1:
                raise OSError("temporary failure")

        send.side_effect = deliver
        completed = threading.Event()
        successes: set[str] = set()

        def result(_generation, server_id, ok, _detail):
            if ok:
                successes.add(server_id)
                if len(successes) == 2:
                    completed.set()

        engine = MetadataDeliveryEngine(result, retry_delays=(0.01,))
        engine.publish([(first, "a"), (second, "b")], "Artist - Title")
        self.assertTrue(completed.wait(1))
        engine.stop()
        self.assertEqual(attempts[first.id], 1)
        self.assertEqual(attempts[second.id], 2)


if __name__ == "__main__":
    unittest.main()
