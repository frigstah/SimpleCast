from __future__ import annotations

import base64
import socket
import ssl
from dataclasses import dataclass

from .models import ServerProfile
from .shoutcast import ShoutcastLoginError, open_source, source_port


@dataclass(frozen=True, slots=True)
class DiagnosticStep:
    name: str
    ok: bool
    detail: str


def run_server_diagnostic(
    server: ServerProfile,
    password: str,
    timeout: float = 5.0,
) -> list[DiagnosticStep]:
    if server.server_type.startswith("shoutcast"):
        return _run_shoutcast_diagnostic(server, password, timeout)

    results: list[DiagnosticStep] = []
    try:
        addresses = socket.getaddrinfo(server.host, server.port, type=socket.SOCK_STREAM)
        address = addresses[0][4][0]
        results.append(DiagnosticStep("Server address", True, f"Resolved to {address}"))
    except OSError as error:
        return [DiagnosticStep("Server address", False, f"Could not resolve: {error}")]

    connection: socket.socket | None = None
    try:
        connection = socket.create_connection((server.host, server.port), timeout=timeout)
        results.append(DiagnosticStep("Server port", True, f"Connected to port {server.port}"))
        if server.use_tls:
            context = ssl.create_default_context()
            connection = context.wrap_socket(connection, server_hostname=server.host)
            results.append(DiagnosticStep("Secure connection", True, "TLS certificate accepted"))

        token = base64.b64encode(
            f"{server.username}:{password}".encode("utf-8")
        ).decode("ascii")
        request = (
            f"PUT {server.mount} HTTP/1.1\r\n"
            f"Host: {server.host}:{server.port}\r\n"
            f"Authorization: Basic {token}\r\n"
            "Content-Type: audio/mpeg\r\n"
            "Ice-Name: SimpleCast connection test\r\n"
            "Expect: 100-continue\r\n"
            "Connection: close\r\n\r\n"
        )
        connection.sendall(request.encode("ascii", errors="replace"))
        response = connection.recv(2048).decode("latin-1", errors="replace")
        status_line = response.splitlines()[0] if response else "No response"
        accepted = any(code in status_line for code in (" 100 ", " 200 ", " 201 "))
        if accepted:
            results.append(
                DiagnosticStep(
                    "Source login",
                    True,
                    "Credentials accepted. The test mount was closed immediately.",
                )
            )
        elif " 401 " in status_line or " 403 " in status_line:
            results.append(
                DiagnosticStep("Source login", False, "Username or password was rejected.")
            )
        elif " 409 " in status_line:
            results.append(
                DiagnosticStep(
                    "Source login",
                    False,
                    "This stream path is already in use.",
                )
            )
        else:
            results.append(
                DiagnosticStep(
                    "Source login",
                    False,
                    f"Server replied: {status_line}",
                )
            )
    except ssl.SSLCertVerificationError as error:
        results.append(DiagnosticStep("Secure connection", False, str(error)))
    except OSError as error:
        results.append(DiagnosticStep("Server connection", False, str(error)))
    finally:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
    return results


def _run_shoutcast_diagnostic(
    server: ServerProfile,
    password: str,
    timeout: float,
) -> list[DiagnosticStep]:
    results: list[DiagnosticStep] = []
    port = source_port(server)
    if not 1 <= port <= 65535:
        return [
            DiagnosticStep(
                "Source port",
                False,
                "Port + 1 is outside the valid range. Turn off port + 1 or change the port.",
            )
        ]
    try:
        addresses = socket.getaddrinfo(server.host, port, type=socket.SOCK_STREAM)
        address = addresses[0][4][0]
        results.append(DiagnosticStep("Server address", True, f"Resolved to {address}"))
    except OSError as error:
        return [DiagnosticStep("Server address", False, f"Could not resolve: {error}")]

    connection: socket.socket | None = None
    try:
        connection = open_source(server, password, bitrate=192, timeout=timeout)
        results.append(
            DiagnosticStep("Source port", True, f"Connected to source port {port}")
        )
        if server.use_tls:
            results.append(
                DiagnosticStep("Secure connection", True, "TLS certificate accepted")
            )
        results.append(
            DiagnosticStep(
                "Source login",
                True,
                "Credentials accepted. The test source was closed immediately.",
            )
        )
    except ShoutcastLoginError as error:
        results.append(DiagnosticStep("Source login", False, str(error)))
    except ssl.SSLCertVerificationError as error:
        results.append(DiagnosticStep("Secure connection", False, str(error)))
    except OSError as error:
        results.append(DiagnosticStep("Server connection", False, str(error)))
    finally:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
    return results
