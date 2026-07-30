from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .models import ServerProfile


class ButtImportError(ValueError):
    """Raised when a file is not a usable BUTT configuration export."""


@dataclass(frozen=True, slots=True)
class ButtServer:
    profile: ServerProfile
    password: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ButtServerExport:
    servers: tuple[ButtServer, ...]
    selected_server_name: str = ""
    skipped: tuple[str, ...] = ()


_SERVER_TYPES = {
    "0": "shoutcast1",
    "shoutcast": "shoutcast1",
    "shoutcast1": "shoutcast1",
    "1": "icecast2",
    "icecast": "icecast2",
    "icecast2": "icecast2",
}


def load_butt_server_export(path: str | Path) -> ButtServerExport:
    """Load only server profiles from a BUTT configuration export."""

    export_path = Path(path)
    try:
        raw = export_path.read_bytes()
    except OSError as exc:
        raise ButtImportError(f"Could not read the selected file: {exc}") from exc
    if len(raw) > 5_000_000:
        raise ButtImportError("The selected file is too large to be a BUTT export.")

    text = _decode_export(raw)
    parser = configparser.ConfigParser(
        interpolation=None,
        strict=False,
        delimiters=("=",),
        comment_prefixes=("#", ";"),
        inline_comment_prefixes=None,
    )
    parser.optionxform = str.lower
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise ButtImportError(
            "The selected file is not a valid BUTT configuration export."
        ) from exc

    if not parser.has_section("main"):
        raise ButtImportError(
            "The selected file has no BUTT server list ([main] / srv_ent)."
        )
    names = [
        name.strip()
        for name in parser.get("main", "srv_ent", fallback="").split(";")
        if name.strip()
    ]
    if not names:
        raise ButtImportError("The selected BUTT export contains no servers.")

    imported: list[ButtServer] = []
    skipped: list[str] = []
    for name in names:
        if not parser.has_section(name):
            skipped.append(f"{name}: server section is missing")
            continue
        section = parser[name]
        server_type = _SERVER_TYPES.get(section.get("type", "").strip().lower())
        if server_type is None:
            skipped.append(f"{name}: unsupported server type")
            continue
        try:
            port = int(section.get("port", "").strip())
        except ValueError:
            skipped.append(f"{name}: invalid port")
            continue

        raw_mount = section.get("mount", "").strip()
        if raw_mount.casefold() == "(none)":
            raw_mount = ""
        if server_type == "icecast2" and not raw_mount:
            skipped.append(f"{name}: Icecast stream path is missing")
            continue

        profile = ServerProfile(
            name=name,
            server_type=server_type,
            host=section.get("address", "").strip(),
            port=port,
            mount=raw_mount,
            username=(
                section.get(
                    "usr",
                    section.get("username", section.get("user", "source")),
                ).strip()
                if server_type == "icecast2"
                else ""
            ),
            # BUTT is a SHOUTcast 1 source client. Its password field may
            # already contain username/password/SID compatibility syntax, so
            # preserve that field verbatim instead of translating it.
            shoutcast_port_plus_one=True,
            use_tls=_as_bool(section.get("tls", "0")),
        ).normalized()
        errors = profile.validate()
        if errors:
            skipped.append(f"{name}: {' '.join(errors)}")
            continue
        imported.append(
            ButtServer(
                profile=profile,
                password=section.get("password", "").strip(),
            )
        )

    return ButtServerExport(
        servers=tuple(imported),
        selected_server_name=parser.get(
            "main",
            "server",
            fallback="",
        ).strip(),
        skipped=tuple(skipped),
    )


def exclude_existing_butt_servers(
    imported: Iterable[ButtServer],
    existing: Iterable[ButtServer],
) -> tuple[tuple[ButtServer, ...], int]:
    """Return import entries that are not exact copies of saved profiles."""

    known = {_server_key(item) for item in existing}
    additions: list[ButtServer] = []
    duplicate_count = 0
    for item in imported:
        key = _server_key(item)
        if key in known:
            duplicate_count += 1
            continue
        known.add(key)
        additions.append(item)
    return tuple(additions), duplicate_count


def _server_key(item: ButtServer) -> tuple[object, ...]:
    profile = item.profile
    return (
        profile.name.casefold(),
        profile.server_type,
        profile.host.casefold(),
        profile.port,
        profile.mount,
        profile.username,
        profile.stream_id,
        profile.shoutcast_port_plus_one,
        profile.use_tls,
        item.password,
    )


def _decode_export(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ButtImportError("The selected BUTT export uses an unsupported encoding.")


def _as_bool(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "yes", "on"}
