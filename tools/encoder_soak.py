from __future__ import annotations

import argparse
import json
import math
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import imageio_ffmpeg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simplecast.processing import PROCESSING_PRESETS
from simplecast.recording import Mp3FileWriter


def run_soak(
    seconds: int,
    sample_rate: int,
    processing: str,
    output: Path,
) -> dict[str, object]:
    block_frames = 1024
    channels = 2
    writer = Mp3FileWriter(output, sample_rate, processing)
    writer.start(sample_rate, channels)
    started = time.monotonic()
    frames_written = 0
    try:
        while time.monotonic() - started < seconds:
            block = bytearray()
            for offset in range(block_frames):
                frame = frames_written + offset
                left = int(
                    11000
                    * math.sin(2 * math.pi * 440 * frame / sample_rate)
                )
                right = int(
                    9000
                    * math.sin(2 * math.pi * 660 * frame / sample_rate)
                )
                block.extend(struct.pack("<hh", left, right))
            writer.write(bytes(block))
            frames_written += block_frames
            target = started + frames_written / sample_rate
            remaining = target - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
    finally:
        writer.close()

    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    decode = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(output),
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        startupinfo=startup,
        check=False,
        timeout=max(30, seconds),
    )
    elapsed = time.monotonic() - started
    return {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "requested_seconds": seconds,
        "elapsed_seconds": round(elapsed, 3),
        "sample_rate": sample_rate,
        "channels": channels,
        "processing": processing,
        "frames_written": frames_written,
        "output_bytes": output.stat().st_size,
        "decode_passed": decode.returncode == 0,
        "decode_error": decode.stderr.decode(
            "utf-8",
            errors="replace",
        ).strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a real-time SimpleCast MP3 encoder endurance check."
    )
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument(
        "--sample-rate",
        type=int,
        choices=(32000, 44100, 48000),
        default=48000,
    )
    parser.add_argument(
        "--processing",
        choices=tuple(PROCESSING_PRESETS),
        default="Mixed content",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error("--seconds must be at least 1")
    output = args.output or (
        Path(tempfile.gettempdir()) / "SimpleCast-encoder-soak.mp3"
    )
    result = run_soak(
        args.seconds,
        args.sample_rate,
        args.processing,
        output,
    )
    report_path = output.with_suffix(".json")
    report_path.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    print(f"Report: {report_path}")
    return 0 if result["decode_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
