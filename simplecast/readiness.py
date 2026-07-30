from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .audio import AudioDevice
from .encoder import get_ffmpeg_exe
from .models import AppConfig
from .processing import PROCESSING_PRESETS
from .program_audio import AudioProgram, process_loopback_supported
from .streaming import QUALITY_PRESETS


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    name: str
    status: str
    detail: str


def _writable_location(path: Path) -> bool:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.exists() and os.access(candidate, os.W_OK)


def _ffmpeg_capabilities() -> tuple[bool, str]:
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    executable = get_ffmpeg_exe()
    outputs: list[str] = []
    return_codes: list[int] = []
    for listing in ("-encoders", "-filters"):
        completed = subprocess.run(
            [executable, "-hide_banner", listing],
            capture_output=True,
            startupinfo=startup,
            check=False,
            timeout=15,
        )
        return_codes.append(completed.returncode)
        outputs.append(
            (completed.stdout + completed.stderr).decode(
                "utf-8",
                errors="replace",
            )
        )
    output = "\n".join(outputs)
    ready = (
        all(return_code == 0 for return_code in return_codes)
        and "libmp3lame" in output
        and "alimiter" in output
    )
    return ready, (
        "MP3 encoder and safety limiter are available."
        if ready
        else "Bundled FFmpeg is missing MP3 or limiter support."
    )


def _signature_check() -> ReadinessCheck:
    if not getattr(sys, "frozen", False):
        return ReadinessCheck(
            "Publisher signature",
            "Warning",
            "Source build; signing is checked on the packaged executable.",
        )
    escaped = str(Path(sys.executable)).replace("'", "''")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                (
                    "(Get-AuthenticodeSignature -LiteralPath "
                    f"'{escaped}').Status"
                ),
            ],
            capture_output=True,
            text=True,
            startupinfo=startup,
            check=False,
            timeout=10,
        )
        status = completed.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        status = "Unknown"
    if status == "Valid":
        return ReadinessCheck(
            "Publisher signature",
            "Pass",
            "The application has a valid Authenticode signature.",
        )
    return ReadinessCheck(
        "Publisher signature",
        "Warning",
        f"Authenticode status: {status or 'NotSigned'}.",
    )


def run_readiness_checks(
    config: AppConfig,
    devices: list[AudioDevice],
    passwords: dict[str, str],
    config_root: Path,
    recording_folder: Path,
    programs: list[AudioProgram] | None = None,
) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []
    windows = platform.system() == "Windows"
    checks.append(
        ReadinessCheck(
            "Windows",
            "Pass" if windows else "Fail",
            platform.platform(),
        )
    )
    checks.append(
        ReadinessCheck(
            "Audio input",
            "Pass" if devices else "Fail",
            (
                f"{len(devices)} recording device(s) available."
                if devices
                else "No recording device is available."
            ),
        )
    )
    if config.program_audio_enabled:
        available_programs = programs or []
        selected_program_available = any(
            item.executable.casefold()
            == config.selected_program_path.casefold()
            for item in available_programs
        )
        program_ready = (
            process_loopback_supported()
            and bool(config.selected_program_path)
            and selected_program_available
        )
        checks.append(
            ReadinessCheck(
                "Program audio",
                "Pass" if program_ready else "Fail",
                (
                    f"{config.selected_program_name} is available through "
                    "Windows WASAPI process loopback."
                    if program_ready
                    else "Open the saved program and refresh the Source list. "
                    "Program audio requires Windows build 20348 or newer."
                ),
            )
        )
    ffmpeg_ready, ffmpeg_detail = _ffmpeg_capabilities()
    checks.append(
        ReadinessCheck(
            "Bundled encoder",
            "Pass" if ffmpeg_ready else "Fail",
            ffmpeg_detail,
        )
    )
    checks.append(
        ReadinessCheck(
            "Settings folder",
            "Pass" if _writable_location(config_root) else "Fail",
            str(config_root),
        )
    )
    checks.append(
        ReadinessCheck(
            "Recording folder",
            "Pass" if _writable_location(recording_folder) else "Fail",
            str(recording_folder),
        )
    )
    enabled = config.enabled_servers()
    server_errors = [
        f"{server.name}: {error}"
        for server in enabled
        for error in server.validate()
    ]
    missing_passwords = [
        server.name for server in enabled if not passwords.get(server.id)
    ]
    if not enabled:
        station_status = "Warning"
        station_detail = "No station is included for broadcasting."
    elif server_errors:
        station_status = "Fail"
        station_detail = " ".join(server_errors)
    elif missing_passwords:
        station_status = "Fail"
        station_detail = "Missing password: " + ", ".join(missing_passwords)
    else:
        station_status = "Pass"
        station_detail = f"{len(enabled)} included station(s) are configured."
    checks.append(
        ReadinessCheck("Station configuration", station_status, station_detail)
    )
    format_ready = (
        config.quality in QUALITY_PRESETS
        and config.processing_preset in PROCESSING_PRESETS
        and config.output_sample_rate in {32000, 44100, 48000}
    )
    checks.append(
        ReadinessCheck(
            "Audio format",
            "Pass" if format_ready else "Fail",
            (
                f"{config.quality}, {config.output_sample_rate / 1000:g} kHz, "
                f"{config.processing_preset}"
            ),
        )
    )
    checks.append(_signature_check())
    return checks
