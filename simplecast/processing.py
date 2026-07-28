from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .encoder import get_ffmpeg_exe

@dataclass(frozen=True, slots=True)
class ProcessingPreset:
    description: str
    ffmpeg_filter: str


PROCESSING_PRESETS = {
    "Off / Original": ProcessingPreset(
        "No processing; preserve the input exactly.",
        "",
    ),
    "Voice": ProcessingPreset(
        "Clear speech with controlled volume and peak limiting.",
        (
            "highpass=f=80,lowpass=f=12000,"
            "acompressor=threshold=0.125:ratio=3:attack=10:"
            "release=150:makeup=1.5,"
            "alimiter=limit=0.95:attack=5:release=50"
        ),
    ),
    "Music": ProcessingPreset(
        "Gentle level control that keeps music dynamics.",
        (
            "acompressor=threshold=0.25:ratio=2:attack=20:"
            "release=250:makeup=1.25,"
            "alimiter=limit=0.95:attack=5:release=80"
        ),
    ),
    "Mixed content": ProcessingPreset(
        "Balanced processing for speech, jingles, and music.",
        (
            "highpass=f=40,"
            "acompressor=threshold=0.18:ratio=2.5:attack=15:"
            "release=200:makeup=1.35,"
            "alimiter=limit=0.95:attack=5:release=65"
        ),
    ),
}

DEFAULT_PROCESSING_PRESET = "Off / Original"


def filter_arguments(preset_name: str) -> list[str]:
    preset = PROCESSING_PRESETS.get(
        preset_name,
        PROCESSING_PRESETS[DEFAULT_PROCESSING_PRESET],
    )
    return ["-af", preset.ffmpeg_filter] if preset.ffmpeg_filter else []


def process_test_file(
    source: Path,
    destination: Path,
    preset_name: str,
) -> None:
    """Create a WAV preview using the same filter used by live encoders."""
    preset = PROCESSING_PRESETS.get(
        preset_name,
        PROCESSING_PRESETS[DEFAULT_PROCESSING_PRESET],
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not preset.ffmpeg_filter:
        shutil.copyfile(source, destination)
        return
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    completed = subprocess.run(
        [
            get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            preset.ffmpeg_filter,
            "-codec:a",
            "pcm_s16le",
            str(destination),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        startupinfo=startup,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "FFmpeg could not create the processed preview.")
