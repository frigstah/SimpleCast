from __future__ import annotations

import logging
import queue
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from .audio import (
    GainControl,
    PcmAudioSource,
    ReverbControl,
    create_audio_source,
)
from .encoder import get_ffmpeg_exe
from .models import ServerProfile
from .processing import DEFAULT_PROCESSING_PRESET, filter_arguments
from .recording import Mp3FileWriter
from .shoutcast import open_source


class BroadcastState(str, Enum):
    OFFLINE = "Offline"
    CONNECTING = "Connecting"
    ON_AIR = "On Air"
    RECONNECTING = "Reconnecting"
    ERROR = "Needs attention"


@dataclass(frozen=True, slots=True)
class QualityPreset:
    bitrate: int
    channels: int | None


QUALITY_PRESETS = {
    "SL Standard": QualityPreset(128, None),
    "SL MAX unsafe": QualityPreset(192, None),
    "Recording": QualityPreset(320, None),
}


@dataclass(frozen=True, slots=True)
class StreamDestination:
    server: ServerProfile
    password: str


@dataclass(frozen=True, slots=True)
class _AudioFormat:
    sample_rate: int
    channels: int


class StreamEngine:
    def __init__(
        self,
        state_callback: Callable[[BroadcastState, str], None],
        level_callback: Callable[[float, float], None],
        gain: GainControl | None = None,
        device_resolver: Callable[[object], object] | None = None,
        recording_callback: Callable[[bool, str, Path | None], None] | None = None,
        program_gain: GainControl | None = None,
        reverb: ReverbControl | None = None,
    ) -> None:
        self.state_callback = state_callback
        self.level_callback = level_callback
        self.gain = gain or GainControl()
        self.device_resolver = device_resolver or (lambda device: device)
        self.recording_callback = recording_callback or (lambda *_: None)
        self.program_gain = program_gain or GainControl()
        self.reverb = reverb or ReverbControl()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._shoutcast_socket: socket.socket | None = None
        self.started_at: float | None = None
        self.recording_started_at: float | None = None
        self.recording_path: Path | None = None

    @property
    def active(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(
        self,
        device: object,
        server: ServerProfile,
        password: str,
        quality: str,
        output_sample_rate: int = 44100,
        audio_system: str = "Automatic",
        recording_path: Path | None = None,
        processing_preset: str = DEFAULT_PROCESSING_PRESET,
    ) -> None:
        if self.active:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(
                device,
                server,
                password,
                quality,
                output_sample_rate,
                audio_system,
                recording_path,
                processing_preset,
            ),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        process = self._process
        if process:
            try:
                process.terminate()
            except OSError:
                pass
        connection = self._shoutcast_socket
        if connection:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.close()
            except OSError:
                pass

    def close(self) -> None:
        self.stop()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=4.5)

    def _run(
        self,
        device: object,
        server: ServerProfile,
        password: str,
        quality: str,
        output_sample_rate: int,
        audio_system: str,
        recording_path: Path | None,
        processing_preset: str,
    ) -> None:
        delay = 2
        first_attempt = True
        recorder: Mp3FileWriter | None = None
        recording_failed = False
        try:
            while not self._stop.is_set():
                state = BroadcastState.CONNECTING if first_attempt else BroadcastState.RECONNECTING
                self.state_callback(state, f"Connecting to {server.name}…")
                source: PcmAudioSource | None = None
                pump_errors: list[Exception] = []
                try:
                    resolved_device = self.device_resolver(device)
                    source = create_audio_source(
                        resolved_device,
                        self.gain,
                        audio_system,
                        self.program_gain,
                        self.reverb,
                    )
                    source.start()
                    if recording_path is not None and recorder is None and not recording_failed:
                        try:
                            recorder = Mp3FileWriter(
                                recording_path,
                                output_sample_rate,
                                processing_preset,
                            )
                            recorder.start(source.sample_rate, source.channels)
                            self.recording_path = recording_path
                            self.recording_started_at = time.monotonic()
                            self.recording_callback(
                                True,
                                f"Recording broadcast to {recording_path.name}",
                                recording_path,
                            )
                        except Exception as error:
                            logging.exception("Could not start broadcast recording")
                            recording_failed = True
                            recorder = None
                            self.recording_callback(
                                False,
                                f"Recording could not start: {error}",
                                recording_path,
                            )
                    preset = QUALITY_PRESETS.get(
                        quality,
                        QUALITY_PRESETS["SL Standard"],
                    )
                    if server.server_type.startswith("shoutcast"):
                        self._shoutcast_socket = open_source(
                            server, password, preset.bitrate
                        )
                    self._process = self._start_ffmpeg(
                        source,
                        server,
                        password,
                        quality,
                        output_sample_rate,
                        processing_preset,
                    )
                    if self._shoutcast_socket is not None:
                        assert self._process.stdout is not None
                        threading.Thread(
                            target=self._pump_shoutcast,
                            args=(
                                self._process.stdout,
                                self._shoutcast_socket,
                                pump_errors,
                            ),
                            daemon=True,
                        ).start()
                    self.started_at = time.monotonic()
                    self.state_callback(
                        BroadcastState.ON_AIR,
                        f"Live on {server.name} · {source.active_api}",
                    )
                    delay = 2
                    while not self._stop.is_set():
                        if self._process.poll() is not None:
                            raise RuntimeError(self._ffmpeg_error(self._process))
                        if pump_errors:
                            raise RuntimeError(f"SHOUTcast connection closed: {pump_errors[0]}")
                        self.level_callback(*source.levels, source.peak_level)
                        try:
                            block = source.blocks.get(timeout=0.25)
                            if recorder is not None:
                                try:
                                    recorder.write(block)
                                except Exception as error:
                                    logging.exception("Broadcast recording failed")
                                    try:
                                        recorder.close()
                                    except Exception:
                                        logging.exception("Could not finalize failed recording")
                                    recorder = None
                                    recording_failed = True
                                    self.recording_started_at = None
                                    self.recording_callback(
                                        False,
                                        f"Recording failed: {error}",
                                        recording_path,
                                    )
                            assert self._process.stdin is not None
                            self._process.stdin.write(block)
                            self._process.stdin.flush()
                        except queue.Empty:
                            if source.failure:
                                raise RuntimeError(source.failure)
                        except (BrokenPipeError, OSError) as error:
                            if self._stop.is_set():
                                break
                            raise RuntimeError(self._ffmpeg_error(self._process)) from error
                    break
                except Exception as error:
                    if self._stop.is_set():
                        logging.info("Broadcast stopped")
                        break
                    logging.exception("Broadcast attempt failed")
                    self.state_callback(
                        BroadcastState.RECONNECTING,
                        f"Connection lost: {error}. Retrying in {delay}s.",
                    )
                    self._stop.wait(delay)
                    delay = min(delay * 2, 30)
                    first_attempt = False
                finally:
                    if source is not None:
                        source.stop()
                    if self._process:
                        process = self._process
                        try:
                            if process.stdin is not None:
                                try:
                                    process.stdin.close()
                                except OSError:
                                    pass
                            process.terminate()
                            process.wait(timeout=2)
                        except (OSError, subprocess.TimeoutExpired):
                            try:
                                process.kill()
                            except OSError:
                                pass
                        for pipe in (process.stdout, process.stderr):
                            if pipe is not None:
                                try:
                                    pipe.close()
                                except OSError:
                                    pass
                        self._process = None
                    if self._shoutcast_socket is not None:
                        try:
                            self._shoutcast_socket.close()
                        except OSError:
                            pass
                        self._shoutcast_socket = None
        finally:
            if recorder is not None:
                try:
                    recorder.close()
                except Exception:
                    logging.exception("Could not finalize the broadcast recording")
            if self.recording_path is not None and not recording_failed:
                self.recording_callback(
                    False,
                    f"Saved {self.recording_path.name}",
                    self.recording_path,
                )
            self.recording_started_at = None
            self.recording_path = None
        self.started_at = None
        self.state_callback(BroadcastState.OFFLINE, "Ready to broadcast")

    @staticmethod
    def _ffmpeg_error(process: subprocess.Popen[bytes]) -> str:
        if process.stderr:
            try:
                detail = process.stderr.read().decode("utf-8", errors="replace").strip()
                lines = [line for line in detail.splitlines() if line.strip()]
                return lines[-1] if lines else "The server closed the connection"
            except OSError:
                pass
        return "The server closed the connection"

    def _start_ffmpeg(
        self,
        source: PcmAudioSource,
        server: ServerProfile,
        password: str,
        quality: str,
        output_sample_rate: int = 44100,
        processing_preset: str = DEFAULT_PROCESSING_PRESET,
    ) -> subprocess.Popen[bytes]:
        preset = QUALITY_PRESETS.get(
            quality,
            QUALITY_PRESETS["SL Standard"],
        )
        channels = preset.channels or source.channels
        if server.server_type.startswith("shoutcast"):
            command = [
                get_ffmpeg_exe(),
                "-hide_banner",
                "-loglevel",
                "warning",
                "-f",
                "s16le",
                "-ar",
                str(source.sample_rate),
                "-ac",
                str(source.channels),
                "-i",
                "pipe:0",
                "-vn",
                *filter_arguments(processing_preset),
                "-ac",
                str(channels),
                "-ar",
                str(output_sample_rate),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                f"{preset.bitrate}k",
                "-f",
                "mp3",
                "pipe:1",
            ]
            return self._spawn_ffmpeg(command, stdout=subprocess.PIPE)

        user = quote(server.username, safe="")
        secret = quote(password, safe="")
        host = server.host.strip("[]")
        url = f"icecast://{user}:{secret}@{host}:{server.port}{server.mount}"
        command = [
            get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "s16le",
            "-ar",
            str(source.sample_rate),
            "-ac",
            str(source.channels),
            "-i",
            "pipe:0",
            "-vn",
            *filter_arguments(processing_preset),
            "-ac",
            str(channels),
            "-ar",
            str(output_sample_rate),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            f"{preset.bitrate}k",
            "-content_type",
            "audio/mpeg",
            "-tls",
            "1" if server.use_tls else "0",
            "-ice_name",
            server.station_name or server.name,
            "-ice_description",
            server.description,
            "-ice_genre",
            server.genre,
            "-ice_url",
            server.website,
            "-f",
            "mp3",
            url,
        ]
        return self._spawn_ffmpeg(command, stdout=subprocess.DEVNULL)

    @staticmethod
    def _spawn_ffmpeg(
        command: list[str],
        stdout: int,
    ) -> subprocess.Popen[bytes]:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=stdout,
            stderr=subprocess.PIPE,
            startupinfo=startup,
        )

    @staticmethod
    def _pump_shoutcast(
        encoded_audio: object,
        connection: socket.socket,
        errors: list[Exception],
    ) -> None:
        try:
            while True:
                chunk = encoded_audio.read(16 * 1024)
                if not chunk:
                    return
                connection.sendall(chunk)
        except Exception as error:
            errors.append(error)


class _ServerWorker:
    """Owns one encoder/connection so failures remain isolated per server."""

    def __init__(
        self,
        destination: StreamDestination,
        audio_format: _AudioFormat,
        quality: str,
        output_sample_rate: int,
        processing_preset: str,
        state_callback: Callable[[str, BroadcastState, str], None],
    ) -> None:
        self.destination = destination
        self.audio_format = audio_format
        self.quality = quality
        self.output_sample_rate = output_sample_rate
        self.processing_preset = processing_preset
        self.state_callback = state_callback
        self.blocks: queue.Queue[bytes] = queue.Queue(maxsize=96)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._connection: socket.socket | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def offer(self, block: bytes) -> None:
        try:
            self.blocks.put_nowait(block)
        except queue.Full:
            try:
                self.blocks.get_nowait()
                self.blocks.put_nowait(block)
            except (queue.Empty, queue.Full):
                pass

    def stop(self) -> None:
        self._stop.set()
        process = self._process
        if process is not None:
            try:
                process.terminate()
            except OSError:
                pass
        connection = self._connection
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.close()
            except OSError:
                pass

    def join(self, timeout: float) -> None:
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        server = self.destination.server
        delay = 2
        first_attempt = True
        encoder = StreamEngine(lambda *_: None, lambda *_: None)
        while not self._stop.is_set():
            state = (
                BroadcastState.CONNECTING
                if first_attempt
                else BroadcastState.RECONNECTING
            )
            self.state_callback(
                server.id,
                state,
                f"{state.value}: {server.name}",
            )
            pump_errors: list[Exception] = []
            try:
                while True:
                    self.blocks.get_nowait()
            except queue.Empty:
                pass
            try:
                preset = QUALITY_PRESETS.get(
                    self.quality,
                    QUALITY_PRESETS["SL Standard"],
                )
                if server.server_type.startswith("shoutcast"):
                    self._connection = open_source(
                        server,
                        self.destination.password,
                        preset.bitrate,
                    )
                self._process = encoder._start_ffmpeg(
                    self.audio_format,
                    server,
                    self.destination.password,
                    self.quality,
                    self.output_sample_rate,
                    self.processing_preset,
                )
                if self._connection is not None:
                    assert self._process.stdout is not None
                    threading.Thread(
                        target=StreamEngine._pump_shoutcast,
                        args=(
                            self._process.stdout,
                            self._connection,
                            pump_errors,
                        ),
                        daemon=True,
                    ).start()
                self.state_callback(
                    server.id,
                    BroadcastState.ON_AIR,
                    f"On air: {server.name}",
                )
                delay = 2
                while not self._stop.is_set():
                    if self._process.poll() is not None:
                        raise RuntimeError(
                            StreamEngine._ffmpeg_error(self._process)
                        )
                    if pump_errors:
                        raise RuntimeError(
                            f"SHOUTcast connection closed: {pump_errors[0]}"
                        )
                    try:
                        block = self.blocks.get(timeout=0.25)
                    except queue.Empty:
                        continue
                    assert self._process.stdin is not None
                    self._process.stdin.write(block)
                    self._process.stdin.flush()
            except Exception as error:
                if not self._stop.is_set():
                    logging.exception("Stream failed for %s", server.name)
                    self.state_callback(
                        server.id,
                        BroadcastState.RECONNECTING,
                        f"{server.name}: {error}. Retrying in {delay}s.",
                    )
                    self._stop.wait(delay)
                    delay = min(delay * 2, 30)
                    first_attempt = False
            finally:
                self._close_connection()
        self.state_callback(
            server.id,
            BroadcastState.OFFLINE,
            f"Stopped: {server.name}",
        )

    def _close_connection(self) -> None:
        process = self._process
        self._process = None
        if process is not None:
            try:
                if process.stdin is not None:
                    try:
                        process.stdin.close()
                    except OSError:
                        pass
                process.terminate()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except OSError:
                        pass
        connection = self._connection
        self._connection = None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


class MultiStreamEngine:
    """Captures audio once and fans it out to independent server workers."""

    def __init__(
        self,
        state_callback: Callable[[BroadcastState, str], None],
        server_state_callback: Callable[[str, BroadcastState, str], None],
        level_callback: Callable[[float, float], None],
        gain: GainControl | None = None,
        device_resolver: Callable[[object], object] | None = None,
        recording_callback: Callable[[bool, str, Path | None], None] | None = None,
        program_gain: GainControl | None = None,
        reverb: ReverbControl | None = None,
    ) -> None:
        self.state_callback = state_callback
        self.server_state_callback = server_state_callback
        self.level_callback = level_callback
        self.gain = gain or GainControl()
        self.device_resolver = device_resolver or (lambda device: device)
        self.recording_callback = recording_callback or (lambda *_: None)
        self.program_gain = program_gain or GainControl()
        self.reverb = reverb or ReverbControl()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._source: PcmAudioSource | None = None
        self._workers: dict[str, _ServerWorker] = {}
        self._statuses: dict[str, tuple[BroadcastState, str]] = {}
        self._status_lock = threading.Lock()
        self.started_at: float | None = None
        self.recording_started_at: float | None = None
        self.recording_path: Path | None = None

    @property
    def active(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def server_statuses(self) -> dict[str, tuple[BroadcastState, str]]:
        with self._status_lock:
            return dict(self._statuses)

    @property
    def online_server_ids(self) -> list[str]:
        with self._status_lock:
            return [
                server_id
                for server_id, (state, _detail) in self._statuses.items()
                if state == BroadcastState.ON_AIR
            ]

    def start(
        self,
        device: object,
        destinations: list[StreamDestination],
        quality: str,
        output_sample_rate: int = 44100,
        audio_system: str = "Automatic",
        recording_path: Path | None = None,
        processing_preset: str = DEFAULT_PROCESSING_PRESET,
    ) -> None:
        if self.active or not destinations:
            return
        self._stop.clear()
        with self._status_lock:
            self._statuses = {
                item.server.id: (
                    BroadcastState.CONNECTING,
                    f"Waiting to connect: {item.server.name}",
                )
                for item in destinations
            }
        self._thread = threading.Thread(
            target=self._run,
            args=(
                device,
                destinations,
                quality,
                output_sample_rate,
                audio_system,
                recording_path,
                processing_preset,
            ),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        for worker in list(self._workers.values()):
            worker.stop()

    def close(self) -> None:
        self.stop()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=4.5)

    def _run(
        self,
        device: object,
        destinations: list[StreamDestination],
        quality: str,
        output_sample_rate: int,
        audio_system: str,
        recording_path: Path | None,
        processing_preset: str,
    ) -> None:
        source: PcmAudioSource | None = None
        recorder: Mp3FileWriter | None = None
        recording_failed = False
        try:
            resolved_device = self.device_resolver(device)
            source = create_audio_source(
                resolved_device,
                self.gain,
                audio_system,
                self.program_gain,
                self.reverb,
            )
            self._source = source
            source.start()
            if recording_path is not None:
                try:
                    recorder = Mp3FileWriter(
                        recording_path,
                        output_sample_rate,
                        processing_preset,
                    )
                    recorder.start(source.sample_rate, source.channels)
                    self.recording_path = recording_path
                    self.recording_started_at = time.monotonic()
                    self.recording_callback(
                        True,
                        f"Recording broadcast to {recording_path.name}",
                        recording_path,
                    )
                except Exception as error:
                    logging.exception("Could not start broadcast recording")
                    recorder = None
                    recording_failed = True
                    self.recording_callback(
                        False,
                        f"Recording could not start: {error}",
                        recording_path,
                    )
            audio_format = _AudioFormat(source.sample_rate, source.channels)
            self._workers = {
                item.server.id: _ServerWorker(
                    item,
                    audio_format,
                    quality,
                    output_sample_rate,
                    processing_preset,
                    self._on_server_state,
                )
                for item in destinations
            }
            self.state_callback(
                BroadcastState.CONNECTING,
                f"Connecting to {len(destinations)} servers…",
            )
            for worker in self._workers.values():
                worker.start()
            while not self._stop.is_set():
                self.level_callback(*source.levels, source.peak_level)
                try:
                    block = source.blocks.get(timeout=0.25)
                except queue.Empty:
                    if source.failure:
                        raise RuntimeError(source.failure)
                    continue
                if recorder is not None:
                    try:
                        recorder.write(block)
                    except Exception as error:
                        logging.exception("Broadcast recording failed")
                        try:
                            recorder.close()
                        except Exception:
                            logging.exception("Could not finalize failed recording")
                        recorder = None
                        recording_failed = True
                        self.recording_started_at = None
                        self.recording_callback(
                            False,
                            f"Recording failed: {error}",
                            recording_path,
                        )
                for worker in list(self._workers.values()):
                    worker.offer(block)
        except Exception as error:
            if not self._stop.is_set():
                logging.exception("Shared broadcast audio failed")
                self.state_callback(
                    BroadcastState.ERROR,
                    f"Audio input failed: {error}",
                )
        finally:
            self._stop.set()
            for worker in list(self._workers.values()):
                worker.stop()
            if recorder is not None:
                try:
                    recorder.close()
                except Exception:
                    logging.exception("Could not finalize the broadcast recording")
                    recording_failed = True
            if self.recording_path is not None and not recording_failed:
                self.recording_callback(
                    False,
                    f"Saved {self.recording_path.name}",
                    self.recording_path,
                )
            deadline = time.monotonic() + 3
            for worker in list(self._workers.values()):
                worker.join(max(0.0, deadline - time.monotonic()))
            if source is not None:
                try:
                    source.stop()
                except Exception:
                    logging.exception("Could not close the shared broadcast input")
            self._source = None
            self._workers = {}
            self.started_at = None
            self.recording_started_at = None
            self.recording_path = None
            self.state_callback(BroadcastState.OFFLINE, "Ready to broadcast")

    def _on_server_state(
        self,
        server_id: str,
        state: BroadcastState,
        detail: str,
    ) -> None:
        with self._status_lock:
            self._statuses[server_id] = (state, detail)
            statuses = list(self._statuses.values())
        self.server_state_callback(server_id, state, detail)
        if self._stop.is_set():
            return
        online = sum(
            item_state == BroadcastState.ON_AIR
            for item_state, _item_detail in statuses
        )
        reconnecting = sum(
            item_state == BroadcastState.RECONNECTING
            for item_state, _item_detail in statuses
        )
        total = len(statuses)
        if online:
            if self.started_at is None:
                self.started_at = time.monotonic()
            summary = f"{online} of {total} servers online"
            if reconnecting:
                summary += f" · {reconnecting} reconnecting"
            self.state_callback(BroadcastState.ON_AIR, summary)
        elif any(
            item_state == BroadcastState.CONNECTING
            for item_state, _item_detail in statuses
        ):
            self.state_callback(
                BroadcastState.CONNECTING,
                f"Connecting to {total} servers…",
            )
        elif not self._stop.is_set():
            self.state_callback(
                BroadcastState.RECONNECTING,
                f"0 of {total} servers online · reconnecting",
            )
