from __future__ import annotations

import logging
import ctypes
import os
import queue
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import numpy as np
import sounddevice as sd


LevelCallback = Callable[..., None]

AUDIO_SYSTEMS = (
    "Automatic",
    "Windows WASAPI (shared)",
    "Windows DirectSound",
    "Windows MME",
)
_audio_thread_state = threading.local()


def _ensure_wasapi_thread() -> None:
    """Initialise COM on the thread that opens a WASAPI stream."""
    if os.name != "nt" or getattr(_audio_thread_state, "com_ready", False):
        return
    result = ctypes.windll.ole32.CoInitializeEx(None, 0x2)  # COINIT_APARTMENTTHREADED
    # S_OK (0), S_FALSE (1), and RPC_E_CHANGED_MODE all mean COM is available
    # on this thread. The latter means another apartment model was chosen first.
    if result not in (0, 1, -2147417850):
        raise OSError(f"Could not initialize Windows COM for WASAPI (0x{result & 0xFFFFFFFF:08X})")
    _audio_thread_state.com_ready = True


class GainControl:
    def __init__(self, percent: int = 100) -> None:
        self._lock = threading.Lock()
        self._multiplier = 1.0
        self.set_percent(percent)

    def set_percent(self, percent: float) -> None:
        with self._lock:
            self._multiplier = max(0.0, min(2.0, float(percent) / 100.0))

    @property
    def multiplier(self) -> float:
        with self._lock:
            return self._multiplier

    def apply(self, data: np.ndarray) -> np.ndarray:
        return np.clip(data * self.multiplier, -1.0, 1.0)


class ReverbControl:
    """Thread-safe microphone reverb settings shared with live capture."""

    def __init__(self, enabled: bool = False, amount_percent: int = 25) -> None:
        self._lock = threading.Lock()
        self._enabled = bool(enabled)
        self._amount = 0.25
        self.set_amount_percent(amount_percent)

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled)

    def set_amount_percent(self, amount_percent: float) -> None:
        with self._lock:
            self._amount = max(
                0.0,
                min(1.0, float(amount_percent) / 100.0),
            )

    @property
    def settings(self) -> tuple[bool, float]:
        with self._lock:
            return self._enabled, self._amount


class SimpleReverb:
    """Small, low-latency multi-tap room effect for microphone audio."""

    _TAPS = (
        (31.0, 0.95),
        (47.0, 0.82),
        (71.0, 0.70),
        (103.0, 0.58),
        (149.0, 0.47),
        (211.0, 0.37),
        (307.0, 0.28),
        (421.0, 0.20),
    )

    def __init__(
        self,
        sample_rate: int,
        channels: int,
        control: ReverbControl,
    ) -> None:
        self.control = control
        self.channels = max(1, int(channels))
        self.delays = tuple(
            max(1, int(round(sample_rate * milliseconds / 1000.0)))
            for milliseconds, _gain in self._TAPS
        )
        self.gains = tuple(gain for _milliseconds, gain in self._TAPS)
        self._gain_total = sum(self.gains)
        self._history = np.zeros(
            (max(self.delays), self.channels),
            dtype=np.float32,
        )
        self._enabled_last_block = False

    def apply(self, data: np.ndarray) -> np.ndarray:
        if data.size == 0:
            return data
        enabled, amount = self.control.settings
        if not enabled or amount <= 0.0:
            if self._enabled_last_block:
                self._history.fill(0.0)
            self._enabled_last_block = False
            return data

        self._enabled_last_block = True
        frames = len(data)
        combined = np.concatenate((self._history, data), axis=0)
        history_frames = len(self._history)
        wet = np.zeros_like(data, dtype=np.float32)
        for delay, gain in zip(self.delays, self.gains):
            start = history_frames - delay
            wet += combined[start:start + frames] * gain
        wet /= self._gain_total

        # A little crossfeed gives stereo microphones a wider room sound while
        # mono devices remain unchanged.
        if self.channels >= 2:
            crossed = wet.copy()
            crossed[:, 0] = wet[:, 0] * 0.82 + wet[:, 1] * 0.18
            crossed[:, 1] = wet[:, 1] * 0.82 + wet[:, 0] * 0.18
            wet = crossed

        self._history = combined[-history_frames:].copy()
        wet_mix = amount * 0.58
        dry_gain = 1.0 - amount * 0.12
        return np.clip(data * dry_gain + wet * wet_mix, -1.0, 1.0)


@dataclass(frozen=True, slots=True)
class CaptureOption:
    index: int
    channels: int
    sample_rate: int
    api_name: str


@dataclass(frozen=True, slots=True)
class AudioDevice:
    index: int
    name: str
    channels: int
    sample_rate: int
    api_name: str = "Windows WASAPI"
    fallbacks: tuple[CaptureOption, ...] = ()

    @property
    def label(self) -> str:
        channel_text = "mono" if self.channels == 1 else "stereo"
        return f"{self.name} · {channel_text}"

    @property
    def capture_options(self) -> tuple[CaptureOption, ...]:
        primary = CaptureOption(
            self.index,
            self.channels,
            self.sample_rate,
            self.api_name,
        )
        return (primary, *self.fallbacks)


@dataclass(frozen=True, slots=True)
class CaptureSelection:
    device: AudioDevice
    program: object | None = None

    @property
    def name(self) -> str:
        program_name = getattr(self.program, "name", "")
        return (
            f"{self.device.name} + {program_name}"
            if program_name
            else self.device.name
        )


class PcmAudioSource(Protocol):
    blocks: queue.Queue[bytes]
    levels: tuple[float, float]
    peak_level: float
    channels: int
    sample_rate: int
    active_api: str
    failure: str

    def start(self) -> None: ...

    def stop(self) -> None: ...


def list_input_devices() -> list[AudioDevice]:
    host_apis = sd.query_hostapis()
    all_devices = list(sd.query_devices())
    groups: dict[str, list[CaptureOption]] = {}
    for index, info in enumerate(all_devices):
        if int(info["max_input_channels"]) <= 0:
            continue
        api_name = str(host_apis[int(info["hostapi"])]["name"])
        if "WDM-KS" in api_name:
            continue
        name = str(info["name"])
        groups.setdefault(name, []).append(
            CaptureOption(
                index=index,
                channels=min(int(info["max_input_channels"]), 2),
                sample_rate=int(info["default_samplerate"] or 48000),
                api_name=api_name,
            )
        )

    def priority(option: CaptureOption) -> int:
        api = option.api_name.upper()
        if "WASAPI" in api:
            return 0
        if "DIRECTSOUND" in api:
            return 1
        if "MME" in api:
            return 2
        return 3

    devices: list[AudioDevice] = []
    for name, options in groups.items():
        ordered = sorted(options, key=priority)
        primary = ordered[0]
        devices.append(
            AudioDevice(
                index=primary.index,
                name=name,
                channels=primary.channels,
                sample_rate=primary.sample_rate,
                api_name=primary.api_name,
                fallbacks=tuple(ordered[1:]),
            )
        )
    return sorted(devices, key=lambda device: device.name.casefold())


def _start_input_stream(
    device: AudioDevice,
    callback: Callable[[np.ndarray, int, object, object], None],
    audio_system: str = "Automatic",
) -> tuple[sd.InputStream, CaptureOption]:
    requested = {
        "Windows WASAPI (shared)": "WASAPI",
        "Windows DirectSound": "DIRECTSOUND",
        "Windows MME": "MME",
    }.get(audio_system)
    options = [
        option
        for option in device.capture_options
        if requested is None or requested in option.api_name.upper()
    ]
    if not options:
        raise sd.PortAudioError(
            f"{audio_system} is not available for “{device.name}”. "
            "Choose Automatic or another audio system."
        )
    if any("WASAPI" in option.api_name.upper() for option in options):
        _ensure_wasapi_thread()
    errors: list[str] = []
    for option in options:
        for attempt in range(2):
            stream: sd.InputStream | None = None
            try:
                settings: dict[str, object] = {}
                if "WASAPI" in option.api_name.upper():
                    settings["extra_settings"] = sd.WasapiSettings(exclusive=False)
                stream = sd.InputStream(
                    device=option.index,
                    channels=option.channels,
                    samplerate=option.sample_rate,
                    dtype="float32",
                    blocksize=0 if "WASAPI" in option.api_name.upper() else 1024,
                    callback=callback,
                    **settings,
                )
                stream.start()
                if option != options[0]:
                    logging.warning(
                        "Using %s fallback for audio device %s",
                        option.api_name,
                        device.name,
                    )
                else:
                    logging.info(
                        "Using %s for audio device %s",
                        option.api_name,
                        device.name,
                    )
                return stream, option
            except sd.PortAudioError as error:
                errors.append(f"{option.api_name}: {error}")
                logging.warning(
                    "%s open attempt %d failed for %s: %s",
                    option.api_name,
                    attempt + 1,
                    device.name,
                    error,
                )
                if stream is not None:
                    try:
                        stream.close()
                    except sd.PortAudioError:
                        pass
                if attempt == 0:
                    time.sleep(0.25)
    raise sd.PortAudioError(
        "Could not open this audio device through any Windows audio API. "
        + " | ".join(errors)
    )


class AudioEngine:
    def __init__(
        self,
        gain: GainControl | None = None,
        program_gain: GainControl | None = None,
        reverb: ReverbControl | None = None,
    ) -> None:
        self._meter_stream: sd.InputStream | None = None
        self._meter_program_source: PcmAudioSource | None = None
        self._meter_program_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._operation_lock = threading.Lock()
        self.gain = gain or GainControl()
        self.program_gain = program_gain or GainControl()
        self.reverb = reverb or ReverbControl()
        self.active_api = ""

    def start_meter(
        self,
        device: object,
        callback: LevelCallback,
        audio_system: str = "Automatic",
    ) -> None:
        with self._operation_lock:
            self._stop_meter_unlocked()
            if not isinstance(device, AudioDevice):
                source = create_audio_source(
                    device,
                    self.gain,
                    audio_system,
                    self.program_gain,
                    self.reverb,
                )
                source.start()
                with self._lock:
                    self._meter_program_source = source
                    self.active_api = source.active_api

                def pump_program_meter() -> None:
                    while self._meter_program_source is source:
                        try:
                            source.blocks.get(timeout=0.1)
                        except queue.Empty:
                            if source.failure:
                                return
                            continue
                        callback(
                            *source.levels,
                            source.peak_level,
                        )

                thread = threading.Thread(
                    target=pump_program_meter,
                    daemon=True,
                )
                self._meter_program_thread = thread
                thread.start()
                return

            effect: SimpleReverb | None = None

            def receive(
                data: np.ndarray,
                _frames: int,
                _time: object,
                _status: object,
            ) -> None:
                nonlocal effect
                if data.size == 0:
                    return
                adjusted = self.gain.apply(data)
                if effect is None:
                    effect = SimpleReverb(
                        device.sample_rate,
                        data.shape[1],
                        self.reverb,
                    )
                adjusted = effect.apply(adjusted)
                rms = np.sqrt(
                    np.mean(np.square(adjusted.astype(np.float64)), axis=0)
                )
                left = float(rms[0])
                right = float(rms[1] if len(rms) > 1 else rms[0])
                callback(
                    left,
                    right,
                    float(np.max(np.abs(adjusted))),
                )

            stream, option = _start_input_stream(device, receive, audio_system)
            with self._lock:
                self._meter_stream = stream
                self.active_api = _display_api(option.api_name)

    def stop_meter(self) -> None:
        with self._operation_lock:
            self._stop_meter_unlocked()

    def _stop_meter_unlocked(self) -> None:
        with self._lock:
            stream = self._meter_stream
            self._meter_stream = None
            program_source = self._meter_program_source
            self._meter_program_source = None
        if stream is not None:
            try:
                # abort() is intentionally used instead of stop(). Some Windows
                # USB/WASAPI drivers wait indefinitely while draining a stream.
                stream.abort()
            finally:
                stream.close()
        if program_source is not None:
            program_source.stop()
        thread = self._meter_program_thread
        self._meter_program_thread = None
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1)

    def record_test(
        self,
        device: object,
        destination: Path,
        seconds: int = 5,
        progress: Callable[[int], None] | None = None,
        audio_system: str = "Automatic",
        level_callback: LevelCallback | None = None,
    ) -> tuple[float, float]:
        self.stop_meter()
        if not isinstance(device, AudioDevice):
            source = create_audio_source(
                device,
                self.gain,
                audio_system,
                self.program_gain,
                self.reverb,
            )
            source.start()
            frames: list[np.ndarray] = []
            started = time.monotonic()
            last_remaining = seconds
            try:
                while time.monotonic() - started < seconds:
                    try:
                        block = source.blocks.get(timeout=0.25)
                    except queue.Empty:
                        if source.failure:
                            raise RuntimeError(source.failure)
                        continue
                    samples = np.frombuffer(block, dtype="<i2").reshape(
                        -1,
                        source.channels,
                    )
                    frames.append(samples.astype(np.float32) / 32768.0)
                    if level_callback:
                        level_callback(
                            *source.levels,
                            source.peak_level,
                        )
                    if progress:
                        remaining = max(
                            0,
                            seconds - int(time.monotonic() - started),
                        )
                        if remaining != last_remaining:
                            last_remaining = remaining
                            progress(remaining)
            finally:
                source.stop()
            data = (
                np.concatenate(frames, axis=0)
                if frames
                else np.zeros((1, source.channels), dtype=np.float32)
            )
            peak = np.max(np.abs(data), axis=0)
            rms = np.sqrt(
                np.mean(np.square(data.astype(np.float64)), axis=0)
            )
            pcm = np.clip(data * 32767, -32768, 32767).astype("<i2")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(destination), "wb") as output:
                output.setnchannels(source.channels)
                output.setsampwidth(2)
                output.setframerate(source.sample_rate)
                output.writeframes(pcm.tobytes())
            self.active_api = source.active_api
            return float(np.max(rms)), float(np.max(peak))

        frames: list[np.ndarray] = []
        started = time.monotonic()
        last_remaining = seconds

        effect: SimpleReverb | None = None

        def receive(data: np.ndarray, _frames: int, _time: object, _status: object) -> None:
            nonlocal effect
            adjusted = self.gain.apply(data)
            if effect is None:
                effect = SimpleReverb(
                    device.sample_rate,
                    data.shape[1],
                    self.reverb,
                )
            adjusted = effect.apply(adjusted)
            frames.append(adjusted)
            if level_callback and adjusted.size:
                levels = np.sqrt(
                    np.mean(
                        np.square(adjusted.astype(np.float64)),
                        axis=0,
                    )
                )
                left = float(levels[0])
                right = float(
                    levels[1] if len(levels) > 1 else levels[0]
                )
                level_callback(
                    left,
                    right,
                    float(np.max(np.abs(adjusted))),
                )
            if progress:
                remaining = max(0, seconds - int(time.monotonic() - started))
                nonlocal last_remaining
                if remaining != last_remaining:
                    last_remaining = remaining
                    progress(remaining)

        stream, option = _start_input_stream(device, receive, audio_system)
        self.active_api = _display_api(option.api_name)
        try:
            sd.sleep(seconds * 1000)
        finally:
            try:
                stream.abort()
            finally:
                stream.close()

        data = (
            np.concatenate(frames, axis=0)
            if frames
            else np.zeros((1, option.channels))
        )
        peak = np.max(np.abs(data), axis=0)
        rms = np.sqrt(np.mean(np.square(data.astype(np.float64)), axis=0))
        pcm = np.clip(data * 32767, -32768, 32767).astype("<i2")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(destination), "wb") as output:
            output.setnchannels(option.channels)
            output.setsampwidth(2)
            output.setframerate(option.sample_rate)
            output.writeframes(pcm.tobytes())
        return float(np.max(rms)), float(np.max(peak))

    @staticmethod
    def play_file(path: Path) -> None:
        with wave.open(str(path), "rb") as source:
            channels = source.getnchannels()
            sample_rate = source.getframerate()
            frames = source.readframes(source.getnframes())
        data = np.frombuffer(frames, dtype="<i2").reshape(-1, channels)
        sd.play(data, sample_rate, blocking=True)


class BroadcastAudioSource:
    """Captures float audio and exposes signed 16-bit PCM blocks."""

    def __init__(
        self,
        device: AudioDevice,
        gain: GainControl | None = None,
        audio_system: str = "Automatic",
        reverb: ReverbControl | None = None,
    ) -> None:
        self.device = device
        self.gain = gain or GainControl()
        self.audio_system = audio_system
        self.reverb = reverb or ReverbControl()
        self.blocks: queue.Queue[bytes] = queue.Queue(maxsize=64)
        self.stream: sd.InputStream | None = None
        self.levels = (0.0, 0.0)
        self.peak_level = 0.0
        self.failure = ""
        self.channels = device.channels
        self.sample_rate = device.sample_rate
        self.active_api = ""

    def start(self) -> None:
        effect: SimpleReverb | None = None

        def receive(data: np.ndarray, _frames: int, _time: object, _status: object) -> None:
            nonlocal effect
            adjusted = self.gain.apply(data)
            if effect is None:
                effect = SimpleReverb(
                    self.sample_rate,
                    data.shape[1],
                    self.reverb,
                )
            adjusted = effect.apply(adjusted)
            rms = np.sqrt(
                np.mean(np.square(adjusted.astype(np.float64)), axis=0)
            )
            self.levels = (
                float(rms[0]),
                float(rms[1] if len(rms) > 1 else rms[0]),
            )
            self.peak_level = float(np.max(np.abs(adjusted)))
            pcm = (adjusted * 32767).astype("<i2").tobytes()
            try:
                self.blocks.put_nowait(pcm)
            except queue.Full:
                try:
                    self.blocks.get_nowait()
                    self.blocks.put_nowait(pcm)
                except queue.Empty:
                    pass

        stream, option = _start_input_stream(
            self.device,
            receive,
            self.audio_system,
        )
        self.stream = stream
        self.channels = option.channels
        self.sample_rate = option.sample_rate
        self.active_api = _display_api(option.api_name)

    def stop(self) -> None:
        if self.stream:
            stream = self.stream
            self.stream = None
            try:
                stream.abort()
            finally:
                stream.close()


def _display_api(api_name: str) -> str:
    return "Windows WASAPI (shared)" if "WASAPI" in api_name.upper() else api_name


def create_audio_source(
    target: object,
    gain: GainControl | None = None,
    audio_system: str = "Automatic",
    program_gain: GainControl | None = None,
    reverb: ReverbControl | None = None,
) -> PcmAudioSource:
    from .program_audio import (
        AudioProgram,
        MixedAudioSource,
        ProgramAudioSource,
    )

    if isinstance(target, AudioProgram):
        return ProgramAudioSource(target, gain)
    if isinstance(target, CaptureSelection):
        if target.program is None:
            return BroadcastAudioSource(
                target.device,
                gain,
                audio_system,
                reverb,
            )
        if not isinstance(target.program, AudioProgram):
            raise TypeError("Unsupported program audio source")
        return MixedAudioSource(
            target.device,
            target.program,
            gain,
            program_gain,
            audio_system,
            reverb,
        )
    if isinstance(target, AudioDevice):
        return BroadcastAudioSource(target, gain, audio_system, reverb)
    raise TypeError("Unsupported audio source")
