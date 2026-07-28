from __future__ import annotations

import base64
import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from .models import ServerProfile


METADATA_FORMATS = (
    "As written",
    "Artist - Title (first two lines)",
)


def send_now_playing(
    server: ServerProfile,
    password: str,
    song: str,
    timeout: float = 5,
) -> None:
    scheme = "https" if server.use_tls else "http"
    if server.server_type.startswith("shoutcast"):
        query = urllib.parse.urlencode(
            {
                "sid": server.stream_id,
                "mode": "updinfo",
                "song": song,
                "pass": password,
            }
        )
        url = f"{scheme}://{server.host}:{server.port}/admin.cgi?{query}"
    else:
        query = urllib.parse.urlencode(
            {"mount": server.mount, "mode": "updinfo", "song": song}
        )
        url = f"{scheme}://{server.host}:{server.port}/admin/metadata?{query}"
    request = urllib.request.Request(url)
    if server.server_type == "icecast2":
        token = base64.b64encode(
            f"{server.username}:{password}".encode("utf-8")
        ).decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
    request.add_header("User-Agent", "SimpleCast/0.7")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status >= 400:
            raise RuntimeError(f"Server returned HTTP {response.status}")


def sanitized_server_json(server: ServerProfile) -> str:
    return json.dumps(server.to_dict(), indent=2, ensure_ascii=False)


def format_metadata_text(raw: str, mode: str) -> str:
    lines = [
        " ".join(line.strip().split())
        for line in raw.lstrip("\ufeff").splitlines()
        if line.strip()
    ]
    if not lines:
        return ""
    if mode == "Artist - Title (first two lines)" and len(lines) >= 2:
        return f"{lines[0]} - {lines[1]}"
    return " ".join(lines)


class MetadataFileWatcher:
    def __init__(
        self,
        title_callback: Callable[[str], None],
        status_callback: Callable[[str], None],
        poll_seconds: float = 1.0,
    ) -> None:
        self.title_callback = title_callback
        self.status_callback = status_callback
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_title = ""

    @property
    def active(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self, path: Path, mode: str) -> None:
        self.stop()
        self._stop.clear()
        self._last_title = ""
        self._thread = threading.Thread(
            target=self._run,
            args=(path, mode),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        self._thread = None

    def _run(self, path: Path, mode: str) -> None:
        last_problem = ""
        while not self._stop.is_set():
            try:
                raw = path.read_text(encoding="utf-8-sig", errors="replace")
                title = format_metadata_text(raw, mode)
                if not title:
                    problem = "Metadata file is empty"
                    if problem != last_problem:
                        self.status_callback(problem)
                        last_problem = problem
                else:
                    if last_problem:
                        self.status_callback("Watching for title changes…")
                    last_problem = ""
                    if title != self._last_title:
                        self._last_title = title
                        self.title_callback(title)
            except FileNotFoundError:
                problem = "Waiting for the metadata file to appear"
                if problem != last_problem:
                    self.status_callback(problem)
                    last_problem = problem
            except OSError as error:
                problem = f"Could not read metadata file: {error}"
                if problem != last_problem:
                    self.status_callback(problem)
                    last_problem = problem
            self._stop.wait(self.poll_seconds)


class MetadataDeliveryEngine:
    """Delivers a title independently, retrying only failed servers."""

    def __init__(
        self,
        result_callback: Callable[[int, str, bool, str], None],
        retry_delays: tuple[float, ...] = (2, 5, 10, 30),
    ) -> None:
        self.result_callback = result_callback
        self.retry_delays = retry_delays
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._generation = 0

    def publish(
        self,
        destinations: list[tuple[ServerProfile, str]],
        song: str,
    ) -> int:
        with self._lock:
            self._generation += 1
            generation = self._generation
        for server, password in destinations:
            threading.Thread(
                target=self._deliver,
                args=(generation, server, password, song),
                daemon=True,
            ).start()
        return generation

    def cancel(self) -> int:
        with self._lock:
            self._generation += 1
            return self._generation

    def stop(self) -> None:
        self._stop.set()
        self.cancel()

    def _current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation

    def _deliver(
        self,
        generation: int,
        server: ServerProfile,
        password: str,
        song: str,
    ) -> None:
        attempt = 0
        while not self._stop.is_set() and self._current(generation):
            try:
                send_now_playing(server, password, song)
                self.result_callback(
                    generation,
                    server.id,
                    True,
                    f"Updated {server.name}",
                )
                return
            except Exception as error:
                logging.warning(
                    "Metadata update failed for %s: %s",
                    server.name,
                    error,
                )
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                self.result_callback(
                    generation,
                    server.id,
                    False,
                    f"{server.name}: retrying in {delay:g}s",
                )
                attempt += 1
                deadline = time.monotonic() + delay
                while (
                    time.monotonic() < deadline
                    and not self._stop.is_set()
                    and self._current(generation)
                ):
                    self._stop.wait(min(0.25, deadline - time.monotonic()))
