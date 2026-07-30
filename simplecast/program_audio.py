from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from .audio import (
    AudioDevice,
    BroadcastAudioSource,
    GainControl,
    ReverbControl,
)


PROCESS_LOOPBACK_MINIMUM_BUILD = 20348
PROCESS_LOOPBACK_SAMPLE_RATE = 44100
PROCESS_LOOPBACK_CHANNELS = 2

# Executable names are normalized to lowercase letters and numbers before
# matching. Browsers are included because services such as YouTube Music and
# SoundCloud commonly run in a browser or an installed browser PWA.
KNOWN_AUDIO_PROGRAM_KEYS = frozenset(
    {
        # Browsers
        "arc",
        "brave",
        "chrome",
        "chromium",
        "duckduckgo",
        "firefox",
        "floorp",
        "librewolf",
        "maxthon",
        "msedge",
        "opera",
        "operagx",
        "vivaldi",
        "waterfox",
        "yandex",
        "yandexbrowser",
        # Karaoke
        "karafun",
        "karafunplayer",
        "openkj",
        "sigloskaraokeplayerrecorder",
        "vanbasco",
        # Music and streaming applications
        "amazonmusic",
        "applemusic",
        "deezer",
        "itunes",
        "musicui",
        "plexamp",
        "qobuz",
        "soundcloud",
        "spotify",
        "tidal",
        "youtubemusic",
        # Common local media players
        "aimp",
        "foobar2000",
        "mediamonkey",
        "microsoftmediaplayer",
        "musicbee",
        "potplayer",
        "vlc",
        "winamp",
        "wmplayer",
    }
)

KNOWN_AUDIO_TITLE_PHRASES = (
    "apple music",
    "kara fun",
    "karafun",
    "soundcloud",
    "spotify",
    "tidal",
    "youtube music",
)


@dataclass(frozen=True, slots=True)
class AudioProgram:
    pid: int
    name: str
    executable: str
    window_title: str = ""

    @property
    def label(self) -> str:
        title = " ".join(self.window_title.split())
        if title.casefold() == self.name.casefold():
            title = ""
        detail = f" — {title}" if title else ""
        label = f"{self.name}{detail}"
        if len(label) > 92:
            label = f"{label[:89]}…"
        return label


def is_known_audio_program(program: AudioProgram) -> bool:
    candidates = (
        program.name,
        Path(program.executable).stem,
    )
    if any(
        _program_key(value) in KNOWN_AUDIO_PROGRAM_KEYS
        for value in candidates
    ):
        return True
    title = " ".join(program.window_title.casefold().split())
    return any(phrase in title for phrase in KNOWN_AUDIO_TITLE_PHRASES)


def filter_audio_programs(
    programs: Iterable[AudioProgram],
    *,
    include_all: bool = False,
    always_include_paths: Iterable[str] = (),
) -> list[AudioProgram]:
    items = list(programs)
    if include_all:
        return items
    preserved = {
        path.casefold()
        for path in always_include_paths
        if path
    }
    return [
        program
        for program in items
        if (
            is_known_audio_program(program)
            or program.executable.casefold() in preserved
        )
    ]


def process_loopback_supported() -> bool:
    return (
        os.name == "nt"
        and sys.getwindowsversion().build >= PROCESS_LOOPBACK_MINIMUM_BUILD
    )


def process_loopback_compatibility_message() -> str:
    if os.name != "nt":
        return "Program audio is available only on Windows."
    build = sys.getwindowsversion().build
    if build < PROCESS_LOOPBACK_MINIMUM_BUILD:
        return (
            "Program audio requires Windows 11 or Windows build "
            f"{PROCESS_LOOPBACK_MINIMUM_BUILD} or newer. "
            f"This computer is running build {build}."
        )
    return "Windows WASAPI process loopback"


def _query_process_image(pid: int) -> str:
    process_query_limited_information = 0x1000
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(
        process_query_limited_information,
        False,
        pid,
    )
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        ):
            return ""
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def _list_processes() -> list[tuple[int, int, str]]:
    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessEntry),
    ]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessEntry),
    ]
    kernel32.Process32NextW.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return []
    results: list[tuple[int, int, str]] = []
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return []
        while True:
            results.append(
                (
                    int(entry.th32ProcessID),
                    int(entry.th32ParentProcessID),
                    str(entry.szExeFile),
                )
            )
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return results


def list_audio_programs(
    *,
    include_all: bool = False,
    always_include_paths: Iterable[str] = (),
) -> list[AudioProgram]:
    """Return running programs suitable for process-loopback capture."""

    if os.name != "nt":
        return []
    user32 = ctypes.windll.user32
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    own_pid = os.getpid()
    programs: dict[int, AudioProgram] = {}
    enum_callback = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    def visit(window: int, _parameter: int) -> bool:
        if not user32.IsWindowVisible(window):
            return True
        length = user32.GetWindowTextLengthW(window)
        if length <= 0:
            return True
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(window, title_buffer, length + 1)
        title = title_buffer.value.strip()
        if not title:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
        process_id = int(pid.value)
        if process_id in (0, own_pid) or process_id in programs:
            return True
        executable = _query_process_image(process_id)
        if not executable:
            return True
        name = Path(executable).stem
        if name.casefold() in {"applicationframehost", "shellexperiencehost"}:
            return True
        programs[process_id] = AudioProgram(
            pid=process_id,
            name=name,
            executable=executable,
            window_title=title,
        )
        return True

    callback = enum_callback(visit)
    user32.EnumWindows.argtypes = [enum_callback, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumWindows(callback, 0)

    process_rows = _list_processes()
    known_paths = {
        item.executable.casefold() for item in programs.values()
    }
    windows_root = str(
        Path(os.environ.get("WINDIR", r"C:\Windows")).resolve()
    ).casefold()
    by_path: dict[str, list[tuple[int, int, str]]] = {}
    for process_id, parent_id, fallback_name in process_rows:
        if process_id in (0, own_pid):
            continue
        executable = _query_process_image(process_id)
        if not executable or executable.casefold().startswith(windows_root):
            continue
        if Path(executable).stem.casefold() in {
            "simplecast",
            "simplecast-process-loopback",
        }:
            continue
        by_path.setdefault(executable.casefold(), []).append(
            (process_id, parent_id, fallback_name)
        )
    for normalized_path, candidates in by_path.items():
        if normalized_path in known_paths:
            continue
        candidate_ids = {item[0] for item in candidates}
        process_id, _parent_id, fallback_name = next(
            (
                item
                for item in candidates
                if item[1] not in candidate_ids
            ),
            candidates[0],
        )
        executable = _query_process_image(process_id)
        if not executable:
            continue
        programs[process_id] = AudioProgram(
            pid=process_id,
            name=Path(executable).stem or Path(fallback_name).stem,
            executable=executable,
        )
    ordered = sorted(
        programs.values(),
        key=lambda item: (item.name.casefold(), item.window_title.casefold()),
    )
    return filter_audio_programs(
        ordered,
        include_all=include_all,
        always_include_paths=always_include_paths,
    )


def resolve_audio_program(
    original: AudioProgram,
    programs: list[AudioProgram] | None = None,
) -> AudioProgram:
    available = (
        programs
        if programs is not None
        else list_audio_programs(include_all=True)
    )
    exact = next(
        (
            item
            for item in available
            if item.executable.casefold() == original.executable.casefold()
            and item.window_title == original.window_title
        ),
        None,
    )
    if exact is not None:
        return exact
    same_executable = next(
        (
            item
            for item in available
            if item.executable.casefold() == original.executable.casefold()
        ),
        None,
    )
    if same_executable is not None:
        return same_executable
    raise RuntimeError(
        f"Program “{original.name}” is no longer running. "
        "Open it, then refresh the Source list."
    )


def _helper_path() -> Path:
    packaged_root = getattr(sys, "_MEIPASS", None)
    if packaged_root:
        return (
            Path(packaged_root)
            / "native"
            / "simplecast-process-loopback.exe"
        )
    return (
        Path(__file__).resolve().parent.parent
        / "native"
        / "bin"
        / "simplecast-process-loopback.exe"
    )


def _program_key(value: str) -> str:
    return "".join(
        character
        for character in value.casefold()
        if character.isalnum()
    )


class ProgramAudioSource:
    """PCM source backed by Windows per-process WASAPI loopback capture."""

    def __init__(
        self,
        program: AudioProgram,
        gain: GainControl | None = None,
        sample_rate: int = PROCESS_LOOPBACK_SAMPLE_RATE,
    ) -> None:
        self.program = program
        self.gain = gain or GainControl()
        self.blocks: queue.Queue[bytes] = queue.Queue(maxsize=64)
        self.levels = (0.0, 0.0)
        self.peak_level = 0.0
        self.channels = PROCESS_LOOPBACK_CHANNELS
        self.sample_rate = int(sample_rate)
        self.active_api = "Windows WASAPI process loopback"
        self.failure: str = ""
        self._process: subprocess.Popen[bytes] | None = None
        self._reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._stderr_lines: list[str] = []

    def start(self) -> None:
        if not process_loopback_supported():
            raise RuntimeError(process_loopback_compatibility_message())
        helper = _helper_path()
        if not helper.exists():
            raise RuntimeError(
                "The program-audio component is missing. Reinstall SimpleCast."
            )
        resolved = resolve_audio_program(self.program)
        self.program = resolved
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self._stop.clear()
        self.failure = ""
        self._process = subprocess.Popen(
            [str(helper), str(resolved.pid), str(self.sample_rate)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startup,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._stderr_reader = threading.Thread(
            target=self._read_stderr,
            daemon=True,
        )
        self._stderr_reader.start()
        if not self._ready.wait(timeout=8):
            process = self._process
            detail = " ".join(self._stderr_lines).strip()
            if process is not None and process.poll() is not None:
                detail = detail or "The Windows capture helper stopped."
            self.stop()
            raise RuntimeError(
                detail or "Windows did not open the selected program audio."
            )
        self._reader = threading.Thread(
            target=self._read_audio,
            daemon=True,
        )
        self._reader.start()

    def _read_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        try:
            for raw_line in iter(process.stderr.readline, b""):
                line = raw_line.decode("utf-8", errors="replace").strip()
                if line == "READY":
                    self._ready.set()
                elif line:
                    self._stderr_lines.append(line)
                    logging.info("Program audio helper: %s", line)
        except OSError:
            pass

    def _read_audio(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        carry = b""
        try:
            while not self._stop.is_set():
                chunk = process.stdout.read(8192)
                if not chunk:
                    break
                chunk = carry + chunk
                usable = len(chunk) - (len(chunk) % (self.channels * 2))
                carry = chunk[usable:]
                if usable == 0:
                    continue
                samples = np.frombuffer(
                    chunk[:usable],
                    dtype="<i2",
                ).reshape(-1, self.channels)
                floating = samples.astype(np.float32) / 32768.0
                adjusted = self.gain.apply(floating)
                rms = np.sqrt(
                    np.mean(
                        np.square(adjusted.astype(np.float64)),
                        axis=0,
                    )
                )
                self.levels = (
                    float(rms[0]),
                    float(rms[1]),
                )
                self.peak_level = float(np.max(np.abs(adjusted)))
                pcm = (
                    np.clip(adjusted * 32767, -32768, 32767)
                    .astype("<i2")
                    .tobytes()
                )
                try:
                    self.blocks.put_nowait(pcm)
                except queue.Full:
                    try:
                        self.blocks.get_nowait()
                        self.blocks.put_nowait(pcm)
                    except (queue.Empty, queue.Full):
                        pass
        except OSError as error:
            if not self._stop.is_set():
                self.failure = f"Program audio stopped: {error}"
        finally:
            if not self._stop.is_set() and not self.failure:
                detail = " ".join(self._stderr_lines).strip()
                self.failure = detail or "The selected program audio stopped."

    def stop(self) -> None:
        self._stop.set()
        process = self._process
        self._process = None
        if process is not None:
            if process.poll() is None:
                try:
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
        reader = self._reader
        if reader and reader is not threading.current_thread():
            reader.join(timeout=1)
        stderr_reader = self._stderr_reader
        if stderr_reader and stderr_reader is not threading.current_thread():
            stderr_reader.join(timeout=1)


class MixedAudioSource:
    """Mix a recording device and one Windows program into stereo PCM."""

    def __init__(
        self,
        device: AudioDevice,
        program: AudioProgram,
        device_gain: GainControl | None = None,
        program_gain: GainControl | None = None,
        audio_system: str = "Automatic",
        reverb: ReverbControl | None = None,
    ) -> None:
        self.device = device
        self.program = program
        self.device_gain = device_gain or GainControl()
        self.program_gain = program_gain or GainControl()
        self.audio_system = audio_system
        self.reverb = reverb or ReverbControl()
        self.blocks: queue.Queue[bytes] = queue.Queue(maxsize=64)
        self.levels = (0.0, 0.0)
        self.peak_level = 0.0
        self.channels = 2
        self.sample_rate = device.sample_rate
        self.active_api = ""
        self.failure = ""
        self._device_source: BroadcastAudioSource | None = None
        self._program_source: ProgramAudioSource | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @staticmethod
    def mix_pcm_blocks(
        device_block: bytes,
        device_channels: int,
        program_block: bytes,
    ) -> bytes:
        """Add equally sized device/program PCM blocks into stereo output."""
        device_samples = np.frombuffer(
            device_block,
            dtype="<i2",
        ).reshape(-1, device_channels)
        if device_channels == 1:
            device_stereo = np.repeat(device_samples, 2, axis=1)
        else:
            device_stereo = device_samples[:, :2]
        program_stereo = np.frombuffer(
            program_block,
            dtype="<i2",
        ).reshape(-1, 2)
        if len(device_stereo) != len(program_stereo):
            raise ValueError("Mixed PCM blocks must contain equal frame counts.")
        mixed = (
            device_stereo.astype(np.float32)
            + program_stereo.astype(np.float32)
        ) / 32768.0
        return (
            np.clip(mixed * 32767, -32768, 32767)
            .astype("<i2")
            .tobytes()
        )

    def start(self) -> None:
        self._stop.clear()
        device_source = BroadcastAudioSource(
            self.device,
            self.device_gain,
            self.audio_system,
            self.reverb,
        )
        try:
            device_source.start()
            program_source = ProgramAudioSource(
                self.program,
                self.program_gain,
                sample_rate=device_source.sample_rate,
            )
            program_source.start()
        except Exception:
            device_source.stop()
            raise
        self._device_source = device_source
        self._program_source = program_source
        self.sample_rate = device_source.sample_rate
        self.active_api = (
            f"{device_source.active_api} + WASAPI program audio"
        )
        for source in (device_source, program_source):
            try:
                while True:
                    source.blocks.get_nowait()
            except queue.Empty:
                pass
        self._thread = threading.Thread(
            target=self._mix,
            daemon=True,
        )
        self._thread.start()

    def _mix(self) -> None:
        device_source = self._device_source
        program_source = self._program_source
        if device_source is None or program_source is None:
            return
        program_buffer = bytearray()
        try:
            while not self._stop.is_set():
                try:
                    device_block = device_source.blocks.get(timeout=0.25)
                except queue.Empty:
                    if device_source.failure:
                        raise RuntimeError(device_source.failure)
                    if program_source.failure:
                        raise RuntimeError(program_source.failure)
                    continue

                device_frames = len(device_block) // (
                    device_source.channels * 2
                )
                required_bytes = device_frames * 4
                while (
                    len(program_buffer) < required_bytes
                    and not self._stop.is_set()
                ):
                    try:
                        program_buffer.extend(
                            program_source.blocks.get(timeout=0.03)
                        )
                    except queue.Empty:
                        break
                available = min(len(program_buffer), required_bytes)
                aligned = available - (available % 4)
                program_bytes = bytes(program_buffer[:aligned])
                del program_buffer[:aligned]
                if aligned < required_bytes:
                    program_bytes += bytes(required_bytes - aligned)
                program_stereo = np.frombuffer(
                    program_bytes,
                    dtype="<i2",
                ).reshape(-1, 2)

                pcm = self.mix_pcm_blocks(
                    device_block,
                    device_source.channels,
                    program_stereo.tobytes(),
                )
                mixed = np.frombuffer(
                    pcm,
                    dtype="<i2",
                ).reshape(-1, 2).astype(np.float32) / 32768.0
                mixed = np.clip(mixed, -1.0, 1.0)
                rms = np.sqrt(
                    np.mean(
                        np.square(mixed.astype(np.float64)),
                        axis=0,
                    )
                )
                self.levels = (float(rms[0]), float(rms[1]))
                self.peak_level = float(np.max(np.abs(mixed)))
                try:
                    self.blocks.put_nowait(pcm)
                except queue.Full:
                    try:
                        self.blocks.get_nowait()
                        self.blocks.put_nowait(pcm)
                    except (queue.Empty, queue.Full):
                        pass
                if program_source.failure:
                    raise RuntimeError(program_source.failure)
        except Exception as error:
            if not self._stop.is_set():
                self.failure = f"Mixed audio stopped: {error}"

    def stop(self) -> None:
        self._stop.set()
        for source in (self._device_source, self._program_source):
            if source is not None:
                try:
                    source.stop()
                except Exception:
                    logging.exception("Could not stop a mixed audio source")
        self._device_source = None
        self._program_source = None
        thread = self._thread
        self._thread = None
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2)
