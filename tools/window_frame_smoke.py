from __future__ import annotations

import argparse
import ctypes
import subprocess
import time
from pathlib import Path


GWL_STYLE = -16
WM_CLOSE = 0x0010
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
REQUIRED_NATIVE_FRAME = (
    WS_CAPTION
    | WS_THICKFRAME
    | WS_MINIMIZEBOX
    | WS_MAXIMIZEBOX
    | WS_SYSMENU
)


def _find_window(process_id: int, timeout: float = 20.0) -> int:
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches: list[int] = []

        @callback_type
        def visit(hwnd: int, _parameter: int) -> bool:
            owner_process = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(
                hwnd,
                ctypes.byref(owner_process),
            )
            if (
                owner_process.value == process_id
                and user32.IsWindowVisible(hwnd)
            ):
                matches.append(int(hwnd))
            return True

        user32.EnumWindows(visit, 0)
        if matches:
            return matches[0]
        time.sleep(0.2)
    raise RuntimeError("SimpleCast did not create a visible window in time.")


def run(executable: Path) -> None:
    if not executable.is_file():
        raise FileNotFoundError(executable)
    process = subprocess.Popen([str(executable)], cwd=str(executable.parent))
    try:
        hwnd = _find_window(process.pid)
        get_style = ctypes.windll.user32.GetWindowLongPtrW
        get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
        get_style.restype = ctypes.c_longlong
        style = int(get_style(hwnd, GWL_STYLE))
        has_native_frame = (
            style & REQUIRED_NATIVE_FRAME
        ) == REQUIRED_NATIVE_FRAME
        print(
            f"PID={process.pid} HWND={hwnd} STYLE=0x{style:08X} "
            f"NATIVE_FRAME={has_native_frame}"
        )
        if not has_native_frame:
            raise RuntimeError(
                "The packaged window is missing standard Windows frame styles."
            )
        ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        process.wait(timeout=15)
        print(f"EXIT_CODE={process.returncode}")
        if process.returncode != 0:
            raise RuntimeError(
                f"SimpleCast exited with code {process.returncode}."
            )
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    arguments = parser.parse_args()
    run(arguments.executable.resolve())


if __name__ == "__main__":
    main()
