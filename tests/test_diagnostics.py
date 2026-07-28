import socket
import threading
import unittest

from simplecast.diagnostics import run_server_diagnostic
from simplecast.models import ServerProfile


class FakeIcecast:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.port = self.socket.getsockname()[1]
        self.socket.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self) -> None:
        connection, _address = self.socket.accept()
        with connection:
            connection.recv(4096)
            connection.sendall(self.response)
        self.socket.close()

    def start(self) -> None:
        self.thread.start()


class FakeShoutcast:
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
            self.received += connection.recv(4096)
            connection.sendall(self.response)
            if self.response.startswith(b"OK"):
                self.received += connection.recv(4096)
        self.socket.close()

    def start(self) -> None:
        self.thread.start()


class DiagnosticTests(unittest.TestCase):
    def test_accepts_credentials(self) -> None:
        fake = FakeIcecast(b"HTTP/1.1 100 Continue\r\n\r\n")
        fake.start()
        server = ServerProfile(host="127.0.0.1", port=fake.port, mount="/live")
        results = run_server_diagnostic(server, "secret")
        self.assertTrue(all(result.ok for result in results))

    def test_reports_rejected_credentials(self) -> None:
        fake = FakeIcecast(b"HTTP/1.1 401 Unauthorized\r\n\r\n")
        fake.start()
        server = ServerProfile(host="127.0.0.1", port=fake.port, mount="/live")
        results = run_server_diagnostic(server, "wrong")
        self.assertFalse(results[-1].ok)
        self.assertIn("rejected", results[-1].detail)

    def test_shoutcast2_sends_sid_and_accepts_ok2(self) -> None:
        fake = FakeShoutcast(b"OK2\r\nicy-caps:11\r\n\r\n")
        fake.start()
        server = ServerProfile(
            server_type="shoutcast2",
            host="127.0.0.1",
            port=fake.port,
            username="dj",
            stream_id=2,
            shoutcast_port_plus_one=False,
        ).normalized()
        results = run_server_diagnostic(server, "secret")
        fake.thread.join(timeout=2)
        self.assertTrue(all(result.ok for result in results))
        self.assertIn(b"dj:secret:#2\r\n", fake.received)
        self.assertIn(b"content-type:audio/mpeg", fake.received)

    def test_shoutcast_reports_rejected_password(self) -> None:
        fake = FakeShoutcast(b"invalid password\r\n")
        fake.start()
        server = ServerProfile(
            server_type="shoutcast1",
            host="127.0.0.1",
            port=fake.port,
            shoutcast_port_plus_one=False,
        ).normalized()
        results = run_server_diagnostic(server, "wrong")
        self.assertFalse(results[-1].ok)
        self.assertIn("rejected", results[-1].detail)


if __name__ == "__main__":
    unittest.main()
