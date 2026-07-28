from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def get_ffmpeg_exe() -> str:
    """Return the pinned release encoder or an explicit development override."""
    override = os.environ.get("SIMPLECAST_FFMPEG_EXE", "").strip()
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file():
            return str(candidate)
        raise RuntimeError(
            f"SIMPLECAST_FFMPEG_EXE does not point to a file: {candidate}"
        )

    base = Path(
        getattr(
            sys,
            "_MEIPASS",
            Path(__file__).resolve().parent.parent,
        )
    )
    bundled = base / "vendor" / "ffmpeg" / "ffmpeg.exe"
    if bundled.is_file():
        return str(bundled)

    system_encoder = shutil.which("ffmpeg")
    if system_encoder:
        return system_encoder

    raise RuntimeError(
        "FFmpeg is unavailable. Run .\\prepare-ffmpeg.ps1 before starting "
        "or building SimpleCast."
    )
