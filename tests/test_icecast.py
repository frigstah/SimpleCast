import base64
import socket
import threading
import unittest
from unittest.mock import Mock, patch

from simplecast.icecast import IcecastLoginError, open_source
from simplecast.models import ServerProfile


class FakeIcecast:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.received = b""
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.port = self.socket.getsockname()[1]
        self.socket.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self) -> None:
        connection, _address = self.socket.accept()
        connection.settimeout(2)
        with connection:
            while b"\r\n\r\n" not in self.received:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                self.received += chunk
            connection.sendall(self.response)
            if self.response.startswith(b"HTTP/1.1 100"):
                try:
                    self.received += connection.recv(4096)
                except (OSError, TimeoutError):
                    pass
        self.socket.close()

    def start(self) -> None:
        self.thread.start()


class IcecastSourceTests(unittest.TestCase):
    def test_advertises_exact_encoded_audio_format(self) -> None:
        fake = FakeIcecast(b"HTTP/1.1 100 Continue\r\n\r\n")
        fake.start()
        server = ServerProfile(
            name="My station",
            station_name="Karaoke Radio",
            description="Music and karaoke",
            genre="Pop",
            website="https://radio.example",
            host="127.0.0.1",
            port=fake.port,
            mount="/live",
            username="source",
        )

        connection = open_source(server, "secret", 128, 48000, 2)
        connection.sendall(b"encoded mp3")
        connection.close()
        fake.thread.join(timeout=2)

        request = fake.received.decode("latin-1")
        self.assertIn("PUT /live HTTP/1.1\r\n", request)
        self.assertIn("Ice-Bitrate: 128\r\n", request)
        self.assertIn("Ice-Samplerate: 48000\r\n", request)
        self.assertIn("Ice-Channels: 2\r\n", request)
        self.assertIn(
            "Ice-Audio-Info: ice-bitrate=128;ice-channels=2;"
            "ice-samplerate=48000\r\n",
            request,
        )
        self.assertIn("icy-br: 128\r\n", request)
        self.assertIn("Ice-Name: Karaoke Radio\r\n", request)
        token = base64.b64encode(b"source:secret").decode("ascii")
        self.assertIn(f"Authorization: Basic {token}\r\n", request)
        self.assertNotIn("source:secret", request)
        self.assertTrue(request.endswith("\r\n\r\nencoded mp3"))

    def test_sanitizes_station_metadata_headers(self) -> None:
        fake = FakeIcecast(b"HTTP/1.1 100 Continue\r\n\r\n")
        fake.start()
        server = ServerProfile(
            station_name="Safe name\r\nInjected: no",
            host="127.0.0.1",
            port=fake.port,
            mount="/live show",
        )

        connection = open_source(server, "secret", 192, 44100, 2)
        connection.close()
        fake.thread.join(timeout=2)

        request = fake.received.decode("latin-1")
        self.assertIn("PUT /live%20show HTTP/1.1", request)
        self.assertIn("Ice-Name: Safe name Injected: no\r\n", request)
        self.assertNotIn("\r\nInjected: no\r\n", request)

    def test_reports_rejected_credentials(self) -> None:
        fake = FakeIcecast(b"HTTP/1.1 401 Unauthorized\r\n\r\n")
        fake.start()
        server = ServerProfile(host="127.0.0.1", port=fake.port, mount="/live")

        with self.assertRaisesRegex(IcecastLoginError, "rejected"):
            open_source(server, "wrong", 128, 44100, 2)
        fake.thread.join(timeout=2)

    @patch("simplecast.icecast.ssl.create_default_context")
    @patch("simplecast.icecast.socket.create_connection")
    def test_wraps_secure_sources_in_tls(self, create_connection, create_context) -> None:
        raw_connection = Mock()
        secure_connection = Mock()
        secure_connection.recv.return_value = b"HTTP/1.1 100 Continue\r\n\r\n"
        context = Mock()
        context.wrap_socket.return_value = secure_connection
        create_context.return_value = context
        create_connection.return_value = raw_connection
        server = ServerProfile(
            host="radio.example",
            port=8443,
            mount="/live",
            use_tls=True,
        )

        result = open_source(server, "secret", 320, 48000, 2)

        self.assertIs(result, secure_connection)
        context.wrap_socket.assert_called_once_with(
            raw_connection,
            server_hostname="radio.example",
        )
        secure_connection.settimeout.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()
