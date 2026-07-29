import unittest
from collections.abc import Callable

from simplecast.listener_stats import (
    ListenerStatsUnavailable,
    fetch_listener_count,
)
from simplecast.models import ServerProfile


class FakeResponse:
    def __init__(self, payload: str) -> None:
        self.payload = payload.encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def response_sequence(
    *payloads: str,
) -> tuple[Callable[..., FakeResponse], list[str]]:
    remaining = list(payloads)
    urls: list[str] = []

    def open_request(request: object, timeout: float) -> FakeResponse:
        del timeout
        urls.append(request.full_url)
        return FakeResponse(remaining.pop(0))

    return open_request, urls


class ListenerStatsTests(unittest.TestCase):
    def test_reads_the_matching_icecast_mount(self) -> None:
        opener, urls = response_sequence(
            """
            {
              "icestats": {
                "source": [
                  {"listenurl": "http://radio.example:8000/other", "listeners": 3},
                  {"listenurl": "http://radio.example:8000/live", "listeners": 17}
                ]
              }
            }
            """
        )
        server = ServerProfile(host="radio.example", mount="/live")
        self.assertEqual(fetch_listener_count(server, opener=opener), 17)
        self.assertEqual(
            urls,
            ["http://radio.example:8000/status-json.xsl"],
        )

    def test_accepts_one_icecast_source_object(self) -> None:
        opener, _urls = response_sequence(
            """
            {
              "icestats": {
                "source": {
                  "listenurl": "https://radio.example/live",
                  "listeners": "8"
                }
              }
            }
            """
        )
        server = ServerProfile(
            host="radio.example",
            port=443,
            mount="/live",
            use_tls=True,
        )
        self.assertEqual(fetch_listener_count(server, opener=opener), 8)

    def test_reports_when_icecast_mount_is_not_public(self) -> None:
        opener, _urls = response_sequence(
            """
            {
              "icestats": {
                "source": {
                  "listenurl": "http://radio.example:8000/other",
                  "listeners": 2
                }
              }
            }
            """
        )
        server = ServerProfile(host="radio.example", mount="/live")
        with self.assertRaises(ListenerStatsUnavailable):
            fetch_listener_count(server, opener=opener)

    def test_reads_shoutcast_2_json_stats(self) -> None:
        opener, urls = response_sequence(
            '{"currentlisteners": 21, "peaklisteners": 35}'
        )
        server = ServerProfile(
            server_type="shoutcast2",
            host="radio.example",
            stream_id=2,
        )
        self.assertEqual(fetch_listener_count(server, opener=opener), 21)
        self.assertEqual(
            urls,
            ["http://radio.example:8000/stats?sid=2&json=1"],
        )

    def test_shoutcast_2_selects_the_configured_sid(self) -> None:
        opener, _urls = response_sequence(
            """
            {
              "streams": [
                {"sid": 1, "listeners": 7},
                {"sid": 3, "listeners": 19}
              ]
            }
            """
        )
        server = ServerProfile(
            server_type="shoutcast2",
            host="radio.example",
            stream_id=3,
        )
        self.assertEqual(fetch_listener_count(server, opener=opener), 19)

    def test_shoutcast_2_falls_back_to_legacy_stats(self) -> None:
        opener, urls = response_sequence(
            "<html>JSON disabled</html>",
            "<html><body>12,1,20,100,12,192,Artist - Title</body></html>",
        )
        server = ServerProfile(
            server_type="shoutcast2",
            host="radio.example",
            stream_id=4,
        )
        self.assertEqual(fetch_listener_count(server, opener=opener), 12)
        self.assertEqual(
            urls[-1],
            "http://radio.example:8000/7.html?sid=4",
        )

    def test_reads_shoutcast_1_legacy_stats(self) -> None:
        opener, urls = response_sequence(
            "5,1,10,100,5,128,Artist - Title"
        )
        server = ServerProfile(
            server_type="shoutcast1",
            host="radio.example",
        )
        self.assertEqual(fetch_listener_count(server, opener=opener), 5)
        self.assertEqual(urls, ["http://radio.example:8000/7.html"])


if __name__ == "__main__":
    unittest.main()
