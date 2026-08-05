from __future__ import annotations

import base64
import socket
import ssl
from urllib.parse import quote

from . import __version__
from .models import ServerProfile


class IcecastLoginError(RuntimeError):
    pass


def open_source(
    server: ServerProfile,
    password: str,
    bitrate: int,
    sample_rate: int,
    channels: int,
    timeout: float = 8.0,
) -> socket.socket:
    """Open an Icecast source connection and advertise the encoded format."""

    host = server.host.strip().strip("[]")
    connection = socket.create_connection((host, server.port), timeout=timeout)
    try:
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if server.use_tls:
            context = ssl.create_default_context()
            connection = context.wrap_socket(connection, server_hostname=host)

        token = base64.b64encode(
            f"{server.username}:{password}".encode("utf-8")
        ).decode("ascii")
        mount = quote(server.mount, safe="/%!$&'()*+,;=:@-._~")
        display_host = f"[{host}]" if ":" in host else host
        audio_info = (
            f"ice-bitrate={int(bitrate)};"
            f"ice-channels={int(channels)};"
            f"ice-samplerate={int(sample_rate)}"
        )
        headers = [
            f"PUT {mount} HTTP/1.1",
            f"Host: {display_host}:{server.port}",
            f"Authorization: Basic {token}",
            f"User-Agent: SimpleCast/{__version__}",
            "Content-Type: audio/mpeg",
            f"Ice-Name: {_header_value(server.station_name or server.name)}",
            f"Ice-Description: {_header_value(server.description)}",
            f"Ice-Genre: {_header_value(server.genre)}",
            f"Ice-URL: {_header_value(server.website)}",
            "Ice-Public: 0",
            f"Ice-Bitrate: {int(bitrate)}",
            f"Ice-Samplerate: {int(sample_rate)}",
            f"Ice-Channels: {int(channels)}",
            f"Ice-Audio-Info: {audio_info}",
            f"icy-br: {int(bitrate)}",
            "Expect: 100-continue",
            "Connection: close",
            "",
            "",
        ]
        connection.sendall(
            "\r\n".join(headers).encode("latin-1", errors="replace")
        )
        response = _receive_response(connection)
        status_line = response.splitlines()[0].strip() if response else ""
        if not any(code in status_line for code in (" 100 ", " 200 ", " 201 ")):
            if " 401 " in status_line or " 403 " in status_line:
                raise IcecastLoginError("The source username or password was rejected.")
            if " 409 " in status_line:
                raise IcecastLoginError("This Icecast stream path is already in use.")
            raise IcecastLoginError(
                "Icecast rejected the source connection: "
                f"{status_line or 'no response'}"
            )

        connection.settimeout(None)
        return connection
    except Exception:
        connection.close()
        raise


def _header_value(value: str) -> str:
    """Keep user-entered station text from creating additional HTTP headers."""

    return " ".join(str(value).replace("\x00", "").splitlines()).strip()


def _receive_response(connection: socket.socket) -> str:
    chunks: list[bytes] = []
    size = 0
    while size < 64 * 1024:
        chunk = connection.recv(min(4096, 64 * 1024 - size))
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
        if b"\r\n\r\n" in b"".join(chunks):
            break
    return b"".join(chunks).decode("latin-1", errors="replace")
