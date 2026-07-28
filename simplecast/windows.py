from __future__ import annotations

import ctypes
import os


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


class SleepPreventer:
    """Keeps Windows awake while a broadcast is active."""

    def __init__(self) -> None:
        self.active = False

    def set_broadcasting(self, broadcasting: bool) -> bool:
        if os.name != "nt":
            self.active = broadcasting
            return True
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED if broadcasting else ES_CONTINUOUS
        result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
        if result:
            self.active = broadcasting
            return True
        return False

