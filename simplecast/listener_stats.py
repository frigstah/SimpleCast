from __future__ import annotations

import csv
import html
import io
import json
import re
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from .models import ServerProfile


class ListenerStatsUnavailable(RuntimeError):
    """Raised when a server does not expose a usable listener count."""


def _request_text(
    url: str,
    timeout: float,
    opener: Callable[..., Any],
) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json, text/plain, text/html",
            "User-Agent": "SimpleCast listener monitor",
        },
    )
    with opener(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _as_non_negative_int(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError) as error:
        raise ListenerStatsUnavailable("Listener count was not a number") from error
    if count < 0:
        raise ListenerStatsUnavailable("Listener count was negative")
    return count


def _icecast_listener_count(payload: str, mount: str) -> int:
    try:
        document = json.loads(payload)
        sources = document["icestats"]["source"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ListenerStatsUnavailable(
            "Icecast did not return usable public statistics"
        ) from error

    if isinstance(sources, dict):
        sources = [sources]
    if not isinstance(sources, list):
        raise ListenerStatsUnavailable("Icecast returned an unknown statistics format")

    wanted_mount = urllib.parse.unquote(mount).rstrip("/") or "/"
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_mount = source.get("mount")
        if not source_mount:
            listen_url = str(source.get("listenurl", ""))
            source_mount = urllib.parse.urlparse(listen_url).path
        normalized_mount = urllib.parse.unquote(str(source_mount)).rstrip("/") or "/"
        if normalized_mount == wanted_mount:
            return _as_non_negative_int(source.get("listeners", 0))

    raise ListenerStatsUnavailable(
        f"Icecast public statistics did not list {mount}"
    )


def _icecast_legacy_listener_count(payload: str, mount: str) -> int:
    """Read Icecast's standard status2.xsl CSV compatibility format."""

    rows = list(csv.reader(io.StringIO(payload.lstrip("\ufeff"))))
    header_index = -1
    mount_column = -1
    listeners_column = -1
    for index, row in enumerate(rows):
        normalized = [cell.strip().lower() for cell in row]
        if (
            "mountpoint" in normalized
            and "current listeners" in normalized
        ):
            header_index = index
            mount_column = normalized.index("mountpoint")
            listeners_column = normalized.index("current listeners")
            break
    if header_index < 0:
        raise ListenerStatsUnavailable(
            "Icecast legacy statistics did not include the expected columns"
        )

    wanted_mount = urllib.parse.unquote(mount).rstrip("/") or "/"
    required_column = max(mount_column, listeners_column)
    for row in rows[header_index + 1:]:
        if len(row) <= required_column:
            continue
        source_mount = (
            urllib.parse.unquote(row[mount_column].strip()).rstrip("/")
            or "/"
        )
        if source_mount == wanted_mount:
            return _as_non_negative_int(row[listeners_column].strip())

    raise ListenerStatsUnavailable(
        f"Icecast legacy statistics did not list {mount}"
    )


def _find_shoutcast_listener_count(
    value: Any,
    stream_id: int,
) -> int | None:
    if isinstance(value, dict):
        normalized = {
            str(key).lower().replace("_", ""): item
            for key, item in value.items()
        }
        if "sid" in normalized:
            try:
                if int(normalized["sid"]) != stream_id:
                    return None
            except (TypeError, ValueError):
                pass
        for key in ("currentlisteners", "listeners"):
            if key in normalized:
                try:
                    return _as_non_negative_int(normalized[key])
                except ListenerStatsUnavailable:
                    pass
        for item in value.values():
            result = _find_shoutcast_listener_count(item, stream_id)
            if result is not None:
                return result
    elif isinstance(value, list):
        for item in value:
            result = _find_shoutcast_listener_count(item, stream_id)
            if result is not None:
                return result
    return None


def _shoutcast_json_listener_count(payload: str, stream_id: int) -> int:
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ListenerStatsUnavailable(
            "SHOUTcast did not return JSON statistics"
        ) from error
    count = _find_shoutcast_listener_count(document, stream_id)
    if count is None:
        raise ListenerStatsUnavailable(
            "SHOUTcast statistics did not include a listener count"
        )
    return count


def _shoutcast_legacy_listener_count(payload: str) -> int:
    body_match = re.search(r"<body[^>]*>(.*?)</body>", payload, re.I | re.S)
    text = body_match.group(1) if body_match else payload
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
    first_field = text.split(",", 1)[0].strip()
    return _as_non_negative_int(first_field)


def fetch_listener_count(
    server: ServerProfile,
    timeout: float = 5,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> int:
    """Fetch the current listener count from a saved station's public stats."""

    scheme = "https" if server.use_tls else "http"
    base_url = f"{scheme}://{server.host}:{server.port}"
    if server.server_type == "icecast2":
        try:
            payload = _request_text(
                f"{base_url}/status-json.xsl",
                timeout,
                opener,
            )
            return _icecast_listener_count(payload, server.mount)
        except Exception:
            # Icecast versions before 2.4 do not provide status-json.xsl.
            # Their standard status2.xsl transform exposes the same live
            # mount count as CSV and is intended for machine consumption.
            payload = _request_text(
                f"{base_url}/status2.xsl",
                timeout,
                opener,
            )
            return _icecast_legacy_listener_count(
                payload,
                server.mount,
            )

    if server.server_type == "shoutcast2":
        try:
            payload = _request_text(
                f"{base_url}/stats?sid={server.stream_id}&json=1",
                timeout,
                opener,
            )
            return _shoutcast_json_listener_count(
                payload,
                server.stream_id,
            )
        except Exception:
            # Some SHOUTcast 2 hosts disable JSON but keep the compatible
            # legacy endpoint enabled.
            pass

    suffix = (
        f"?sid={server.stream_id}"
        if server.server_type == "shoutcast2"
        else ""
    )
    payload = _request_text(
        f"{base_url}/7.html{suffix}",
        timeout,
        opener,
    )
    return _shoutcast_legacy_listener_count(payload)
