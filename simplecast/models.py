from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ServerProfile:
    id: str = field(default_factory=lambda: uuid4().hex)
    name: str = "My station"
    server_type: str = "icecast2"
    host: str = ""
    port: int = 8000
    mount: str = "/live"
    username: str = "source"
    stream_id: int = 1
    shoutcast_port_plus_one: bool = True
    use_tls: bool = False
    station_name: str = ""
    description: str = ""
    genre: str = ""
    website: str = ""

    def normalized(self) -> "ServerProfile":
        self.host = self.host.strip()
        self.name = self.name.strip() or "My station"
        if self.server_type not in {"icecast2", "shoutcast1", "shoutcast2"}:
            self.server_type = "icecast2"
        self.username = self.username.strip()
        if self.server_type == "icecast2":
            self.username = self.username or "source"
            mount = self.mount.strip() or "/live"
            self.mount = mount if mount.startswith("/") else f"/{mount}"
        else:
            self.mount = ""
        self.port = int(self.port)
        self.stream_id = max(1, int(self.stream_id))
        return self

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.host:
            errors.append("Enter the server address.")
        if not (1 <= int(self.port) <= 65535):
            errors.append("Port must be between 1 and 65535.")
        if (
            self.server_type.startswith("shoutcast")
            and self.shoutcast_port_plus_one
            and self.port == 65535
        ):
            errors.append("Port + 1 must not exceed 65535.")
        if self.server_type == "icecast2":
            if not self.mount or self.mount == "/":
                errors.append("Enter a stream path such as /live.")
            if not self.username:
                errors.append("Enter the source username.")
        if self.server_type == "shoutcast2" and self.stream_id < 1:
            errors.append("Stream ID must be 1 or higher.")
        return errors

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ServerProfile":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value[key] for key in allowed if key in value}).normalized()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AppConfig:
    selected_device: int | None = None
    selected_device_name: str = ""
    selected_server_id: str = ""
    enabled_server_ids: list[str] = field(default_factory=list)
    quality: str = "SL Standard"
    output_sample_rate: int = 44100
    audio_system: str = "Automatic"
    input_volume_percent: int = 100
    processing_preset: str = "Off / Original"
    recording_folder: str = ""
    record_broadcasts: bool = False
    metadata_file: str = ""
    metadata_auto: bool = False
    metadata_format: str = "As written"
    start_with_windows: bool = False
    start_minimized: bool = False
    auto_broadcast: bool = False
    startup_delay_seconds: int = 10
    servers: list[ServerProfile] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AppConfig":
        try:
            output_sample_rate = int(value.get("output_sample_rate", 44100))
        except (TypeError, ValueError):
            output_sample_rate = 44100
        if output_sample_rate not in {32000, 44100, 48000}:
            output_sample_rate = 44100
        audio_system = value.get("audio_system", "Automatic")
        if audio_system not in {
            "Automatic",
            "Windows WASAPI (shared)",
            "Windows DirectSound",
            "Windows MME",
        }:
            audio_system = "Automatic"
        quality = {
            "Voice": "SL Standard",
            "Standard": "SL MAX unsafe",
            "High quality": "Recording",
        }.get(value.get("quality"), value.get("quality", "SL Standard"))
        if quality not in {"SL Standard", "SL MAX unsafe", "Recording"}:
            quality = "SL Standard"
        processing_preset = str(
            value.get("processing_preset", "Off / Original")
        )
        if processing_preset not in {
            "Off / Original",
            "Voice",
            "Music",
            "Mixed content",
        }:
            processing_preset = "Off / Original"
        metadata_format = str(value.get("metadata_format", "As written"))
        if metadata_format not in {
            "As written",
            "Artist - Title (first two lines)",
        }:
            metadata_format = "As written"
        try:
            startup_delay_seconds = int(
                value.get("startup_delay_seconds", 10)
            )
        except (TypeError, ValueError):
            startup_delay_seconds = 10
        if startup_delay_seconds not in {5, 10, 30, 60}:
            startup_delay_seconds = 10
        servers = [
            ServerProfile.from_dict(item)
            for item in value.get("servers", [])
            if isinstance(item, dict)
        ]
        selected_server_id = str(value.get("selected_server_id", ""))
        raw_enabled = value.get("enabled_server_ids")
        if isinstance(raw_enabled, list):
            enabled_server_ids = [
                str(server_id)
                for server_id in raw_enabled
                if any(server.id == str(server_id) for server in servers)
            ]
        else:
            # Older configurations had one selected server. Preserve that
            # behavior by enabling it as the sole broadcast destination.
            enabled_server_ids = (
                [selected_server_id]
                if any(server.id == selected_server_id for server in servers)
                else []
            )
        if not any(server.id == selected_server_id for server in servers):
            selected_server_id = servers[0].id if servers else ""
        return cls(
            selected_device=value.get("selected_device"),
            selected_device_name=value.get("selected_device_name", ""),
            selected_server_id=selected_server_id,
            enabled_server_ids=enabled_server_ids,
            quality=quality,
            output_sample_rate=output_sample_rate,
            audio_system=audio_system,
            input_volume_percent=max(
                0,
                min(200, int(value.get("input_volume_percent", 100))),
            ),
            processing_preset=processing_preset,
            recording_folder=str(value.get("recording_folder", "")),
            record_broadcasts=bool(value.get("record_broadcasts", False)),
            metadata_file=str(value.get("metadata_file", "")),
            metadata_auto=bool(value.get("metadata_auto", False)),
            metadata_format=metadata_format,
            start_with_windows=bool(value.get("start_with_windows", False)),
            start_minimized=bool(value.get("start_minimized", False)),
            auto_broadcast=bool(value.get("auto_broadcast", False)),
            startup_delay_seconds=startup_delay_seconds,
            servers=servers,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_device": self.selected_device,
            "selected_device_name": self.selected_device_name,
            "selected_server_id": self.selected_server_id,
            "enabled_server_ids": self.enabled_server_ids,
            "quality": self.quality,
            "output_sample_rate": self.output_sample_rate,
            "audio_system": self.audio_system,
            "input_volume_percent": self.input_volume_percent,
            "processing_preset": self.processing_preset,
            "recording_folder": self.recording_folder,
            "record_broadcasts": self.record_broadcasts,
            "metadata_file": self.metadata_file,
            "metadata_auto": self.metadata_auto,
            "metadata_format": self.metadata_format,
            "start_with_windows": self.start_with_windows,
            "start_minimized": self.start_minimized,
            "auto_broadcast": self.auto_broadcast,
            "startup_delay_seconds": self.startup_delay_seconds,
            "servers": [server.to_dict() for server in self.servers],
        }

    def selected_server(self) -> ServerProfile | None:
        return next(
            (server for server in self.servers if server.id == self.selected_server_id),
            None,
        )

    def enabled_servers(self) -> list[ServerProfile]:
        enabled = set(self.enabled_server_ids)
        return [server for server in self.servers if server.id in enabled]
