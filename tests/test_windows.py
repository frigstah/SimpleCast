import unittest
from unittest.mock import Mock, patch

from simplecast.windows import ES_CONTINUOUS, ES_SYSTEM_REQUIRED, SleepPreventer


class SleepPreventerTests(unittest.TestCase):
    @patch("simplecast.windows.os.name", "nt")
    @patch("simplecast.windows.ctypes.windll", create=True)
    def test_sets_and_clears_windows_execution_state(self, windll) -> None:
        setter = Mock(return_value=1)
        windll.kernel32.SetThreadExecutionState = setter
        preventer = SleepPreventer()

        self.assertTrue(preventer.set_broadcasting(True))
        setter.assert_called_with(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        self.assertTrue(preventer.active)

        self.assertTrue(preventer.set_broadcasting(False))
        setter.assert_called_with(ES_CONTINUOUS)
        self.assertFalse(preventer.active)

