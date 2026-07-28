from __future__ import annotations

import os
import subprocess
import sys
import winreg
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "SimpleCast"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        return subprocess.list2cmdline([str(executable), "--startup"])
    executable = Path(sys.executable).resolve()
    script = Path(sys.argv[0]).resolve()
    return subprocess.list2cmdline(
        [str(executable), str(script), "--startup"]
    )


def set_start_with_windows(enabled: bool) -> None:
    if os.name != "nt":
        raise OSError("Windows startup registration is only available on Windows.")
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        if enabled:
            winreg.SetValueEx(
                key,
                VALUE_NAME,
                0,
                winreg.REG_SZ,
                startup_command(),
            )
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass


def is_start_with_windows() -> bool:
    if os.name != "nt":
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_QUERY_VALUE,
        ) as key:
            value, value_type = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    return value_type == winreg.REG_SZ and bool(str(value).strip())
