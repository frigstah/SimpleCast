from __future__ import annotations

import socket
import ssl

from .models import ServerProfile


class ShoutcastLoginError(RuntimeError):
    pass


def source_port(server: ServerProfile) -> int:
    return server.port + 1 if server.shoutcast_port_plus_one else server.port


def source_password(server: ServerProfile, password: str) -> str:
    if server.server_type != "shoutcast2":
        return password
    suffix = f":#{server.stream_id}"
    return (
        f"{server.username}:{password}{suffix}"
        if server.username
        else f"{password}{suffix}"
    )


def open_source(
    server: ServerProfile,
    password: str,
    bitrate: int,
    timeout: float = 8.0,
) -> socket.socket:
    port = source_port(server)
    connection = socket.create_connection((server.host, port), timeout=timeout)
    try:
        if server.use_tls:
            context = ssl.create_default_context()
            connection = context.wrap_socket(connection, server_hostname=server.host)
        connection.sendall(
            (source_password(server, password) + "\r\n").encode(
                "utf-8", errors="replace"
            )
        )
        response = _receive_login_response(connection)
        first_line = response.splitlines()[0].strip() if response else ""
        if first_line not in {"OK", "OK2"}:
            if any(word in response.lower() for word in ("invalid", "bad password")):
                raise ShoutcastLoginError("The source password was rejected.")
            raise ShoutcastLoginError(
                f"SHOUTcast rejected the source login: {first_line or 'no response'}"
            )

        headers = [
            f"icy-name:{server.station_name or server.name}",
            f"icy-genre:{server.genre}",
            "icy-pub:0",
            f"icy-br:{bitrate}",
            f"icy-url:{server.website}",
            "content-type:audio/mpeg",
            "",
            "",
        ]
        connection.sendall(
            "\r\n".join(headers).encode("latin-1", errors="replace")
        )
        connection.settimeout(None)
        return connection
    except Exception:
        connection.close()
        raise


def _receive_login_response(connection: socket.socket) -> str:
    chunks: list[bytes] = []
    size = 0
    while size < 4096:
        chunk = connection.recv(1024)
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
        combined = b"".join(chunks)
        if b"\r\n\r\n" in combined or combined in {b"OK\r\n", b"OK2\r\n"}:
            break
    return b"".join(chunks).decode("latin-1", errors="replace")
