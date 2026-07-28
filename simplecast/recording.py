from __future__ import annotations

import logging
import queue
import subprocess
import threading
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

import imageio_ffmpeg

from .audio import AudioDevice, BroadcastAudioSource, GainControl
from .processing import DEFAULT_PROCESSING_PRESET, filter_arguments


RECORDING_BITRATE = 320


class RecordingState(str, Enum):
    OFFLINE = "Not recording"
    RECORDING = "Recording"
    ERROR = "Recording failed"


def default_recording_folder() -> Path:
    return Path.home() / "Music" / "SimpleCast Recordings"


def next_recording_path(
    folder: Path,
    when: datetime | None = None,
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = (when or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    candidate = folder / f"SimpleCast-{timestamp}.mp3"
    suffix = 2
    while candidate.exists():
        candidate = folder / f"SimpleCast-{timestamp}-{suffix}.mp3"
        suffix += 1
    return candidate


class Mp3FileWriter:
    """Writes signed 16-bit PCM blocks to a finalized 320 kbps MP3 file."""

    def __init__(
        self,
        destination: Path,
        output_sample_rate: int,
        processing_preset: str = DEFAULT_PROCESSING_PRESET,
    ) -> None:
        self.destination = destination
        self.output_sample_rate = output_sample_rate
        self.processing_preset = processing_preset
        self.process: subprocess.Popen[bytes] | None = None

    def start(self, source_sample_rate: int, channels: int) -> None:
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "s16le",
            "-ar",
            str(source_sample_rate),
            "-ac",
            str(channels),
            "-i",
            "pipe:0",
            "-vn",
            *filter_arguments(self.processing_preset),
            "-ac",
            str(channels),
            "-ar",
            str(self.output_sample_rate),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            f"{RECORDING_BITRATE}k",
            "-f",
            "mp3",
            str(self.destination),
        ]
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            startupinfo=startup,
        )

    def write(self, block: bytes) -> None:
        process = self.process
        if process is None or process.stdin is None:
            raise RuntimeError("The recording encoder is not running.")
        if process.poll() is not None:
            raise RuntimeError(self._error_detail(process))
        process.stdin.write(block)
        process.stdin.flush()

    def close(self) -> None:
        process = self.process
        self.process = None
        if process is None:
            return
        failure: str | None = None
        try:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            try:
                return_code = process.wait(timeout=3)
                if return_code not in (0, None):
                    failure = self._error_detail(process)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                failure = "The MP3 encoder did not finish within four seconds."
        finally:
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except OSError:
                        pass
        if failure:
            raise RuntimeError(failure)

    @staticmethod
    def _error_detail(process: subprocess.Popen[bytes]) -> str:
        if process.stderr:
            try:
                detail = process.stderr.read().decode(
                    "utf-8",
                    errors="replace",
                ).strip()
                lines = [line for line in detail.splitlines() if line.strip()]
                if lines:
                    return lines[-1]
            except OSError:
                pass
        return "The MP3 encoder stopped unexpectedly."


class RecordingEngine:
    """Captures an input directly when the user records without broadcasting."""

    def __init__(
        self,
        state_callback: Callable[[RecordingState, str, Path | None], None],
        level_callback: Callable[[float, float], None],
        gain: GainControl | None = None,
        device_resolver: Callable[[AudioDevice], AudioDevice] | None = None,
    ) -> None:
        self.state_callback = state_callback
        self.level_callback = level_callback
        self.gain = gain or GainControl()
        self.device_resolver = device_resolver or (lambda device: device)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._source: BroadcastAudioSource | None = None
        self._writer: Mp3FileWriter | None = None
        self.path: Path | None = None
        self.started_at: float | None = None

    @property
    def active(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def size_bytes(self) -> int:
        try:
            return self.path.stat().st_size if self.path else 0
        except OSError:
            return 0

    def start(
        self,
        device: AudioDevice,
        destination: Path,
        output_sample_rate: int,
        audio_system: str,
        processing_preset: str = DEFAULT_PROCESSING_PRESET,
    ) -> None:
        if self.active:
            return
        self._stop.clear()
        self.path = destination
        self._thread = threading.Thread(
            target=self._run,
            args=(
                device,
                destination,
                output_sample_rate,
                audio_system,
                processing_preset,
            ),
            daemon=True,
        )
        self._thread.start()

    def stop(self, wait_timeout: float = 0.0) -> None:
        self._stop.set()
        thread = self._thread
        if wait_timeout and thread and thread is not threading.current_thread():
            thread.join(timeout=wait_timeout)

    def close(self) -> None:
        self.stop(wait_timeout=4.5)

    def _run(
        self,
        device: AudioDevice,
        destination: Path,
        output_sample_rate: int,
        audio_system: str,
        processing_preset: str,
    ) -> None:
        source: BroadcastAudioSource | None = None
        writer: Mp3FileWriter | None = None
        error: Exception | None = None
        try:
            resolved_device = self.device_resolver(device)
            source = BroadcastAudioSource(
                resolved_device,
                self.gain,
                audio_system,
            )
            self._source = source
            source.start()
            writer = Mp3FileWriter(
                destination,
                output_sample_rate,
                processing_preset,
            )
            self._writer = writer
            writer.start(source.sample_rate, source.channels)
            self.started_at = time.monotonic()
            self.state_callback(
                RecordingState.RECORDING,
                f"Recording to {destination.name} · {source.active_api}",
                destination,
            )
            while not self._stop.is_set():
                self.level_callback(*source.levels, source.peak_level)
                try:
                    block = source.blocks.get(timeout=0.25)
                except queue.Empty:
                    continue
                writer.write(block)
        except Exception as caught:
            error = caught
            if not self._stop.is_set():
                logging.exception("Local recording failed")
        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    logging.exception("Could not finalize the MP3 recording")
                    if error is None:
                        error = RuntimeError("The MP3 file could not be finalized.")
            if source is not None:
                try:
                    source.stop()
                except Exception:
                    logging.exception("Could not close the recording audio source")
            self._source = None
            self._writer = None
            self.started_at = None
            if error is not None and not self._stop.is_set():
                self.state_callback(
                    RecordingState.ERROR,
                    f"Recording failed: {error}",
                    destination,
                )
            else:
                self.state_callback(
                    RecordingState.OFFLINE,
                    f"Saved {destination.name}",
                    destination,
                )
